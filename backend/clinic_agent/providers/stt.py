"""Speech-to-text builders.

Every builder returns a `livekit.agents.stt.STT`. That ABC is the seam - the
rest of the codebase only ever sees it, never a vendor class.
"""

from __future__ import annotations

from collections.abc import Callable

from livekit.agents import stt
from livekit.plugins import elevenlabs, sarvam

from clinic_agent.config import Settings, require_key


def _sarvam(cfg: Settings) -> stt.STT:
    # sarvam.STT declares streaming=True and does its own endpointing over a
    # websocket the plugin owns, so no separate VAD is wired in.
    return sarvam.STT(
        model=cfg.stt_model or "saaras:v4",
        # "unknown" auto-detects per utterance: callers mix Hindi and English.
        language=cfg.stt_language or "unknown",
        mode=cfg.stt_mode,
        sample_rate=cfg.stt_sample_rate,
        api_key=require_key(cfg.sarvam_api_key, "SARVAM_API_KEY"),
    )


def _elevenlabs(cfg: Settings) -> stt.STT:
    # scribe_v2_realtime is the only streaming Scribe model, and streaming is
    # what lets turn detection trust the STT's end of speech, as with Sarvam;
    # the batch models would leave the session with no end-of-turn signal.
    # Without a language it auto-detects; "unknown" (Sarvam's word for that)
    # means the same here, so switching STT_PROVIDER needs no other change.
    language = cfg.stt_language if cfg.stt_language not in (None, "unknown") else None
    options = {"language_code": language} if language else {}
    return elevenlabs.STT(
        model=cfg.stt_model or "scribe_v2_realtime",
        sample_rate=cfg.stt_sample_rate,
        api_key=require_key(cfg.elevenlabs_api_key, "ELEVENLABS_API_KEY"),
        **options,
    )


# Allowed vendors are Sarvam (production) and ElevenLabs. Don't add others.
BUILDERS: dict[str, Callable[[Settings], stt.STT]] = {
    "sarvam": _sarvam,
    "elevenlabs": _elevenlabs,
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
