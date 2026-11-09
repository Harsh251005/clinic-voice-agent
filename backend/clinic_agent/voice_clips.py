"""Recorded phrases: the greeting, fillers and goodbyes are said from a stored
recording while one exists for the call's voice, and by the voice itself
(live, as before) while not. Recording happens only when an admin asks.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from clinic_agent.store import repo
from clinic_agent.store.db import Session


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
