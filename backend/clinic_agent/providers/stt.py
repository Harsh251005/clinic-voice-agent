"""Speech-to-text builders.

Every builder returns a `livekit.agents.stt.STT`. That ABC is the seam - the
rest of the codebase only ever sees it, never a vendor class.
"""

from __future__ import annotations

from collections.abc import Callable

from livekit.agents import stt
from livekit.plugins import sarvam

from clinic_agent.config import Settings, require_key


def _sarvam(cfg: Settings) -> stt.STT:
    # sarvam.STT declares streaming=True and does its own endpointing over a
    # websocket the plugin owns, so no separate VAD is wired in.
    return sarvam.STT(
        model=cfg.sarvam_stt_model or "saaras:v3",
        # Sarvam answers the Hindi line. "unknown" auto-detects per utterance,
        # so the Hinglish callers mix in (English words, whole English
        # sentences) comes through as said; the replies stay Hindi.
        language=cfg.sarvam_stt_language or "unknown",
        mode=cfg.sarvam_stt_mode,
        sample_rate=cfg.stt_sample_rate,
        api_key=require_key(cfg.sarvam_api_key, "SARVAM_API_KEY"),
    )


# Sarvam is the only allowed STT vendor (the Hindi line). Don't add others.
BUILDERS: dict[str, Callable[[Settings], stt.STT]] = {
    "sarvam": _sarvam,
}


def build_stt(cfg: Settings, vendor: str) -> stt.STT:
    """`vendor`'s STT, as the Hindi line names it (clinic_agent/lines.py)."""
    try:
        builder = BUILDERS[vendor]
    except KeyError:
        raise ValueError(f"unknown STT vendor {vendor!r}; available: {sorted(BUILDERS)}") from None
    return builder(cfg)
