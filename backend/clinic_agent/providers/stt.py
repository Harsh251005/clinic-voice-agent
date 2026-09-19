"""Speech-to-text builders.

Every builder returns a `livekit.agents.stt.STT`. That ABC is the seam - the
rest of the codebase only ever sees it, never a vendor class.
"""

from __future__ import annotations

from collections.abc import Callable

from livekit.agents import stt
from livekit.plugins import sarvam

from clinic_agent.config import Settings


def _sarvam(cfg: Settings) -> stt.STT:
    # sarvam.STT declares streaming=True and does its own endpointing over a
    # websocket the plugin owns, so no separate VAD is wired in.
    return sarvam.STT(
        model=cfg.stt_model,
        language=cfg.stt_language,
        mode=cfg.stt_mode,
        sample_rate=cfg.stt_sample_rate,
        api_key=cfg.sarvam_api_key,
    )


BUILDERS: dict[str, Callable[[Settings], stt.STT]] = {
    "sarvam": _sarvam,
}


def build_stt(cfg: Settings) -> stt.STT:
    try:
        builder = BUILDERS[cfg.stt_provider]
    except KeyError:
        raise ValueError(
            f"unknown STT provider {cfg.stt_provider!r}; "
            f"available: {sorted(BUILDERS)}"
        ) from None
    return builder(cfg)
