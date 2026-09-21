"""Text-to-speech builders.

Every builder returns a `livekit.agents.tts.TTS`.
"""

from __future__ import annotations

from collections.abc import Callable

from livekit.agents import tts
from livekit.plugins import elevenlabs, sarvam

from clinic_agent.config import Settings, require_key


def _sarvam(cfg: Settings) -> tts.TTS:
    # The plugin defaults to mp3, which costs a decode on every chunk;
    # linear16 hands LiveKit raw PCM instead. Speaker must be a bulbul:v3 voice.
    return sarvam.TTS(
        model=cfg.tts_model or "bulbul:v3",
        speaker=cfg.tts_speaker or "suhani",
        target_language_code=cfg.tts_language or "en-IN",
        speech_sample_rate=cfg.tts_sample_rate or 24000,
        output_audio_codec=cfg.tts_codec or "linear16",
        api_key=require_key(cfg.sarvam_api_key, "SARVAM_API_KEY"),
    )


def _elevenlabs(cfg: Settings) -> tts.TTS:
    # flash_v2_5 is ElevenLabs' lowest-latency multilingual model and speaks
    # Hindi. pcm_24000 is raw PCM for the same reason as Sarvam's linear16.
    # Language is left to auto-detect unless pinned, since callers mix
    # Hindi and English. TTS_SPEAKER is an ElevenLabs voice ID.
    options = {"language": cfg.tts_language} if cfg.tts_language else {}
    return elevenlabs.TTS(
        model=cfg.tts_model or "eleven_flash_v2_5",
        voice_id=cfg.tts_speaker or elevenlabs.DEFAULT_VOICE_ID,
        encoding=cfg.tts_codec or "pcm_24000",
        api_key=require_key(cfg.elevenlabs_api_key, "ELEVENLABS_API_KEY"),
        **options,
    )


BUILDERS: dict[str, Callable[[Settings], tts.TTS]] = {
    "sarvam": _sarvam,
    "elevenlabs": _elevenlabs,
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
