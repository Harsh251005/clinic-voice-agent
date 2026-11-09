"""Recorded phrases: the greeting, fillers and goodbyes are said from a stored
recording while one exists for the call's voice, and by the voice itself
(live, as before) while not. Recording happens only when an admin asks.
Reliability before savings (Harsh, 2026-11-09): a missing or failed
recording never stops a phrase, it is said live.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from livekit.agents import tts as lk_tts
from livekit.agents.utils import http_context

from clinic_agent import incidents
from clinic_agent.store import repo
from clinic_agent.store.db import Session, Sessions
from clinic_agent.store.models import utc_now

logger = logging.getLogger("clinic-agent.voice-clips")

RECORD_TIMEOUT = 30.0  # seconds for one phrase; Sarvam answers a sentence in about one


def clip_key(voice: dict, text: str) -> str:
    """The recording's name: a hash of everything that changes how `text`
    sounds (providers.identity) and the exact text. A new voice or a single
    changed character is a new key, so an old take never plays by mistake;
    going back to an old voice finds its clips again."""
    parts = [voice[k] for k in ("vendor", "model", "voice", "language_code", "sample_rate", "codec", "pace", "pitch")]
    return hashlib.sha256("\x1f".join(str(p) for p in [*parts, text]).encode()).hexdigest()


@dataclass(frozen=True)
class Said:
    """A phrase ready to say: its words, and its recording if there is one
    for the call's voice (else the voice says the words live)."""

    text: str
    pcm: bytes | None = None
    sample_rate: int = 0


class Phrasebook:
    """Everything fixed a call may say, loaded once at its start so nothing
    reads the database mid-call. Built by `load`."""

    def __init__(self, said: dict[tuple[str, str], list[Said]]) -> None:
        self._said = said
        self._last: dict[str, Said] = {}

    def one(self, kind: str, language: str) -> Said:
        """The phrase of `kind` in `language`; a set of fillers gives one at
        random, never the one said last."""
        options = self._said[(kind, language)]
        fresh = [o for o in options if o != self._last.get(kind + language)] or options
        self._last[kind + language] = choice = random.choice(fresh)
        return choice


def load(s: Session, clinic, languages: Iterable[str], voice_of: Callable[[str], dict]) -> Phrasebook:
    """The clinic's phrases in `languages`, each with its recording for the
    voice `voice_of(language)` (providers.identity) when one exists. The
    greeting's `{clinic}` is the clinic's Hindi name, else its own."""
    said: dict[tuple[str, str], list[Said]] = {}
    for language in languages:
        voice = voice_of(language)
        rows = sorted(repo.phrases_for_call(s, clinic.id, language), key=lambda p: p.slot)
        texts = [p.text.replace("{clinic}", clinic.name_hi or clinic.name) for p in rows]
        clips = repo.clips_by_key(s, [clip_key(voice, t) for t in texts])
        for row, text in zip(rows, texts):
            clip = clips.get(clip_key(voice, text))
            said.setdefault((row.kind, language), []).append(
                Said(text, clip.pcm, clip.sample_rate) if clip else Said(text))
    return Phrasebook(said)


class RecordFailed(RuntimeError):
    """A phrase could not be recorded. The message is for the admin page."""


async def record(sessions: Sessions, voice: lk_tts.TTS, identity: dict, text: str) -> None:
    """Have `voice` say `text` once and keep the recording under its key
    (`identity` is providers.identity(voice)). Its characters are counted on
    the Costs page (Other). A failure opens a problem for the admin and raises
    RecordFailed; the phrase is then still said live on calls."""
    try:
        pcm, sample_rate = await asyncio.wait_for(_synthesize(voice, text), RECORD_TIMEOUT)
    except Exception as err:  # any vendor or network failure: reported, never half-saved
        why = "it took too long" if isinstance(err, TimeoutError) else type(err).__name__
        logger.warning("recording a phrase failed: %s", why)
        await asyncio.to_thread(_report, sessions, identity, why)
        raise RecordFailed(f"The voice could not record this phrase ({why}). Calls say it live meanwhile.") from None
    await asyncio.to_thread(_keep, sessions, identity, text, pcm, sample_rate)


async def _synthesize(voice: lk_tts.TTS, text: str) -> tuple[bytes, int]:
    """One whole synthesis: 16-bit mono PCM and its sample rate."""
    async with http_context.open():
        frame = await voice.synthesize(text).collect()
    if frame.num_channels != 1 or frame.samples_per_channel == 0:
        raise ValueError("no usable audio")
    return bytes(frame.data), frame.sample_rate


def _keep(sessions: Sessions, identity: dict, text: str, pcm: bytes, sample_rate: int) -> None:
    with sessions() as s:
        repo.save_clip(s, key=clip_key(identity, text), vendor=identity["vendor"], model=identity["model"],
                       voice=identity["voice"], language_code=identity["language_code"], sample_rate=sample_rate,
                       text=text, pcm=pcm, duration_s=len(pcm) / 2 / sample_rate)
        repo.add_usage(s, None, utc_now(), "voice_clip", "other", [{
            "provider": identity["vendor"], "model": identity["model"], "unit": "characters", "quantity": float(len(text)),
        }])
        incidents.clear(s, "voice_clip_failed", utc_now(), subject=identity["vendor"])


def _report(sessions: Sessions, identity: dict, why: str) -> None:
    with sessions() as s:
        incidents.report(s, "voice_clip_failed", utc_now(), subject=identity["vendor"], detail=why[:200])
