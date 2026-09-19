"""Every environment-backed setting, read once at startup.

Adding a setting means adding a field here and a line in `load_settings()`.
Nothing else in the codebase should touch `os.environ`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised at startup when the environment is unusable."""


@dataclass(frozen=True)
class Settings:
    # --- credentials ---
    sarvam_api_key: str

    # --- which implementation to build (keys into the provider registries) ---
    stt_provider: str
    llm_provider: str
    tts_provider: str

    # --- speech to text ---
    stt_model: str
    stt_language: str
    stt_mode: str
    stt_sample_rate: int

    # --- language model ---
    llm_model: str

    # --- text to speech ---
    tts_model: str
    tts_speaker: str
    tts_language: str
    tts_sample_rate: int
    tts_codec: str

    # --- turn taking ---
    min_endpointing_delay: float


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"{name} is not set. Copy .env.example to .env and fill it in."
        )
    return value


def _text(name: str, default: str) -> str:
    return os.environ.get(name, "").strip() or default


def _number(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None


def load_settings() -> Settings:
    """Read .env and the environment into a Settings object.

    Fails here rather than at the first utterance, so a missing key is a
    startup error instead of a caller hearing silence.
    """
    load_dotenv()

    return Settings(
        sarvam_api_key=_required("SARVAM_API_KEY"),
        stt_provider=_text("STT_PROVIDER", "sarvam"),
        llm_provider=_text("LLM_PROVIDER", "sarvam"),
        tts_provider=_text("TTS_PROVIDER", "sarvam"),
        stt_model=_text("STT_MODEL", "saaras:v4"),
        stt_language=_text("STT_LANGUAGE", "unknown"),
        stt_mode=_text("STT_MODE", "transcribe"),
        stt_sample_rate=int(_number("STT_SAMPLE_RATE", 16000)),
        llm_model=_text("LLM_MODEL", "sarvam-105b-conversations"),
        tts_model=_text("TTS_MODEL", "bulbul:v3"),
        tts_speaker=_text("TTS_SPEAKER", "anushka"),
        tts_language=_text("TTS_LANGUAGE", "en-IN"),
        tts_sample_rate=int(_number("TTS_SAMPLE_RATE", 24000)),
        tts_codec=_text("TTS_CODEC", "linear16"),
        min_endpointing_delay=_number("MIN_ENDPOINTING_DELAY", 0.2),
    )
