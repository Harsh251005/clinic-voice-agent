"""Recorded phrases: the greeting, fillers and goodbyes are said from a stored
recording while one exists for the call's voice, and by the voice itself
(live, as before) while not. Recording happens only when an admin asks.
"""

from __future__ import annotations

import hashlib


def clip_key(voice: dict, text: str) -> str:
    """The recording's name: a hash of everything that changes how `text`
    sounds (providers.identity) and the exact text. A new voice or a single
    changed character is a new key, so an old take never plays by mistake;
    going back to an old voice finds its clips again."""
    parts = [voice[k] for k in ("vendor", "model", "voice", "language_code", "sample_rate", "codec")]
    return hashlib.sha256("\x1f".join(str(p) for p in [*parts, text]).encode()).hexdigest()
