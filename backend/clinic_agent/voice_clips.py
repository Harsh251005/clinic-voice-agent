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
from dataclasses import dataclass, field, replace

from livekit import rtc
from livekit.agents import tts as lk_tts
from livekit.agents.utils import http_context

from clinic_agent import incidents
from clinic_agent.providers import identity as voice_identity
from clinic_agent.store import repo
from clinic_agent.store.db import Session, Sessions
from clinic_agent.store.models import utc_now

logger = logging.getLogger("clinic-agent.voice-clips")

RECORD_TIMEOUT = 30.0  # seconds for one phrase; Sarvam answers a sentence in about one
FRAME_MS = 100  # a recording is played in frames this long

# Said live when the database has no phrase of a kind (or could not be read):
# a call never goes without its greeting, fillers or goodbye. Same words as
# the seeds in migration 0014; an admin's edits live in the database.
BUILT_IN: dict[tuple[str, str], list[str]] = {
    ("greeting", "hi"): ["नमस्ते, {clinic} में आपका स्वागत है। मैं इसकी ऑटोमेटेड असिस्टेंट हूँ, और यह बातचीत क्लिनिक के "
                         "रिकॉर्ड के लिए टेक्स्ट में सेव हो रही है। बताइए, मैं आपकी कैसे मदद कर सकती हूँ?"],
    ("filler", "hi"): ["एक सेकंड जी, मैं चेक करके बताती हूँ।", "ठीक है, एक पल, मैं देख लेती हूँ।", "जी, बस एक सेकंड।"],
    ("goodbye_fallback", "hi"): ["कॉल करने के लिए धन्यवाद जी। आपका दिन शुभ हो, नमस्ते!"],
    ("goodbye_time_limit", "hi"): ["माफ़ कीजिए जी, इस कॉल का समय पूरा हो गया है। आप दोबारा कॉल कर सकते हैं। नमस्ते!"],
}


def clip_key(voice: dict, text: str) -> str:
    """The recording's name: a hash of everything that changes how `text`
    sounds (providers.identity) and the exact text. A new voice or a single
    changed character is a new key, so an old take never plays by mistake;
    going back to an old voice finds its clips again."""
    parts = [voice[k] for k in ("vendor", "model", "voice", "language_code", "sample_rate", "codec", "pace", "pitch")]
    return hashlib.sha256("\x1f".join(str(p) for p in [*parts, text]).encode()).hexdigest()


def at_pace(voice: dict, pace: float) -> dict:
    """The voice as it records a phrase: its own speed (Phrase.pace), not the
    live voice's, so changing either never un-records the other."""
    return {**voice, "pace": pace}


@dataclass(frozen=True)
class Said:
    """A phrase ready to say: its words, and its recording if there is one
    for the call's voice (else the voice says the words live)."""

    text: str
    pcm: bytes | None = None
    sample_rate: int = 0
    kind: str = field(default="", compare=False)  # greeting, filler, goodbye_fallback, goodbye_time_limit
    # Told the kind when its recording plays (the call's trace notes it: no voice cost).
    heard: Callable[[str], None] | None = field(default=None, compare=False, repr=False)


class Phrasebook:
    """Everything fixed a call may say, loaded once at its start so nothing
    reads the database mid-call. Built by `load`."""

    def __init__(self, said: dict[tuple[str, str], list[Said]] | None = None, clinic_name: str = "") -> None:
        self._said = said or {}
        self._clinic = clinic_name
        self._last: dict[str, Said] = {}
        self.on_play: Callable[[str], None] | None = None  # told each time a recording plays

    def one(self, kind: str, language: str) -> Said:
        """The phrase of `kind` in `language`; a set of fillers gives one at
        random, never the one said last. A kind the database lacks is said
        live in its built-in words."""
        options = self._said.get((kind, language)) or [
            Said(t.replace("{clinic}", self._clinic), kind=kind) for t in BUILT_IN[(kind, language)]]
        fresh = [o for o in options if o != self._last.get(kind + language)] or options
        self._last[kind + language] = choice = random.choice(fresh)
        return replace(choice, heard=self.on_play) if self.on_play else choice


def load(s: Session, clinic, languages: Iterable[str], voice_of: Callable[[str], dict | None]) -> Phrasebook:
    """The clinic's phrases in `languages`, each with its recording for the
    voice `voice_of(language)` (providers.identity) when one exists; None (a
    typed console call has no voice) loads no recordings. The greeting's
    `{clinic}` is the clinic's Hindi name, else its own."""
    name = spoken_name(clinic)
    said: dict[tuple[str, str], list[Said]] = {}
    for language in languages:
        voice = voice_of(language)
        rows = sorted(repo.phrases_for_call(s, clinic.id, language), key=lambda p: p.slot)
        texts = [spoken(p.text, clinic) for p in rows]
        keys = [clip_key(at_pace(voice, p.pace), t) for p, t in zip(rows, texts)] if voice else []
        clips = repo.clips_by_key(s, keys) if voice else {}
        for i, (row, text) in enumerate(zip(rows, texts)):
            clip = clips.get(keys[i]) if voice else None
            said.setdefault((row.kind, language), []).append(
                Said(text, clip.pcm, clip.sample_rate, kind=row.kind) if clip and _playable(clip) else Said(text, kind=row.kind))
    return Phrasebook(said, name)


def spoken_name(clinic) -> str:
    return clinic.name_hi or clinic.name


def spoken(text: str, clinic) -> str:
    """A phrase's words as said on this clinic's calls: `{clinic}` filled in."""
    return text.replace("{clinic}", spoken_name(clinic))


def _playable(clip) -> bool:
    """A stored take that can be played as 16-bit mono PCM; anything else is
    skipped and the phrase is said live."""
    ok = clip.sample_rate > 0 and len(clip.pcm) >= 2 and len(clip.pcm) % 2 == 0
    if not ok:
        logger.warning("voice clip %s is unplayable; saying it live", clip.key[:12])
    return ok


def for_call(sessions: Sessions, clinic, language: str, voice: lk_tts.TTS | None) -> Phrasebook:
    """The call's phrasebook. Reading it never stops a call: on any failure
    the phrases are said live in their built-in words, and the admin is told."""
    try:
        with sessions() as s:
            book = load(s, clinic, [language], lambda _: voice_identity(voice) if voice is not None else None)
            incidents.clear(s, "voice_clips_unread", utc_now(), clinic_id=clinic.id)  # read fine: closes as fixed
            return book
    except Exception as err:  # noqa: BLE001 - the call goes on with live speech
        logger.exception("could not load the voice clips; saying every phrase live")
        try:
            with sessions() as s:
                incidents.report(s, "voice_clips_unread", utc_now(), clinic_id=clinic.id, detail=type(err).__name__)
        except Exception:  # noqa: BLE001 - the database itself is down; the log has it
            logger.exception("could not report the voice clips failure")
        return Phrasebook(clinic_name=spoken_name(clinic))


def say(session, said: Said, **kwargs):
    """Say a phrase: its recording when it has one (no voice vendor call),
    else the voice says the words live. Either way the words are what the
    transcript and the model see. Returns LiveKit's SpeechHandle."""
    if said.pcm:
        if said.heard:
            try:
                said.heard(said.kind)
            except Exception:  # noqa: BLE001 - noting it must never stop the line
                logger.exception("could not note a played recording")
        return session.say(said.text, audio=_frames(said), **kwargs)
    return session.say(said.text, **kwargs)


async def _frames(said: Said):
    step = said.sample_rate * FRAME_MS // 1000 * 2  # bytes per frame (16-bit mono)
    for start in range(0, len(said.pcm), step):
        chunk = said.pcm[start:start + step]
        yield rtc.AudioFrame(chunk, said.sample_rate, 1, len(chunk) // 2)


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


def stale_lines(s: Session, clinic, voice: dict, language: str = "hi") -> int:
    """This clinic's lines recorded in some voice but not in `voice`, its
    current one (at each phrase's own speed): they are said live until
    recorded again, so the admin is told (Harsh, 2026-11-10)."""
    lines = [(p, spoken(p.text, clinic)) for p in repo.phrases_for_call(s, clinic.id, language)]
    ever = repo.recorded_texts(s, [words for _, words in lines])
    current = repo.clip_dates(s, [clip_key(at_pace(voice, p.pace), words) for p, words in lines])
    current_texts = {c.text for c in current.values()}
    return sum(1 for _, words in lines if words in ever and words not in current_texts)
