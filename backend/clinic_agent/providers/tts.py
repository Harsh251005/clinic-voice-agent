"""Text-to-speech builders.

Every builder returns a `livekit.agents.tts.TTS`.
"""

from __future__ import annotations

from collections.abc import Callable

from livekit.agents import tts
from livekit.plugins import sarvam

from clinic_agent.config import Settings


def _sarvam(cfg: Settings) -> tts.TTS:
    # The plugin defaults to mp3, which costs a decode on every chunk;
    # linear16 hands LiveKit raw PCM instead.
    return sarvam.TTS(
        model=cfg.tts_model,
        speaker=cfg.tts_speaker,
        target_language_code=cfg.tts_language,
        speech_sample_rate=cfg.tts_sample_rate,
        output_audio_codec=cfg.tts_codec,
        api_key=cfg.sarvam_api_key,
    )


BUILDERS: dict[str, Callable[[Settings], tts.TTS]] = {
    "sarvam": _sarvam,
}


def build_tts(cfg: Settings) -> tts.TTS:
    try:
        builder = BUILDERS[cfg.tts_provider]
    except KeyError:
        raise ValueError(
            f"unknown TTS provider {cfg.tts_provider!r}; "
            f"available: {sorted(BUILDERS)}"
        ) from None
    return builder(cfg)
