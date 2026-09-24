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
    # --- credentials: each is required only if a selected provider uses it ---
    sarvam_api_key: str
    openai_api_key: str
    elevenlabs_api_key: str

    # --- which implementation to build (keys into the provider registries) ---
    stt_provider: str
    llm_provider: str
    tts_provider: str

    # --- per-vendor settings. Each vendor keeps its own, so switching the
    # stack is only the three *_PROVIDER lines. None = the builder's default ---
    stt_sample_rate: int  # the audio fed to whichever STT runs

    sarvam_stt_model: str | None
    sarvam_stt_language: str | None
    sarvam_stt_mode: str
    elevenlabs_stt_model: str | None
    elevenlabs_stt_language: str | None

    sarvam_llm_model: str | None
    openai_llm_model: str | None

    sarvam_tts_model: str | None
    sarvam_tts_speaker: str | None
    sarvam_tts_language: str | None
    sarvam_tts_sample_rate: int | None
    sarvam_tts_codec: str | None
    elevenlabs_tts_model: str | None
    elevenlabs_tts_voice: str | None
    elevenlabs_tts_language: str | None
    elevenlabs_tts_codec: str | None

    # --- turn taking ---
    min_endpointing_delay: float

    # --- calls ---
    max_call_minutes: float  # then a goodbye and hang up

    # --- dashboard ---
    dashboard_login: str  # "google", or "off" for local development only
    admin_emails: frozenset[str]  # lowercased; see every clinic and manage access
    dashboard_url: str  # where staff open the dashboard, no trailing slash
    session_secret: str  # signs the dashboard session cookie
    google_client_id: str
    google_client_secret: str

    # --- clinic data ---
    database_url: str

    # --- LiveKit (the worker's CLI reads these itself; the call-link server
    # signs join passes with them) ---
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str

    # --- call links ---
    public_base_url: str  # where the call-link server is reachable, no trailing slash
    api_host: str
    api_port: int
    # Header carrying the caller's real IP when behind a proxy or tunnel
    # (e.g. CF-Connecting-IP). Blank = the socket address; never trusted otherwise.
    client_ip_header: str | None


def require_key(value: str, name: str) -> str:
    """Called by a provider builder for the key it needs, so an unused
    vendor's key never has to be set."""
    if not value:
        raise ConfigError(
            f"{name} is not set. Copy .env.example to .env and fill it in."
        )
    return value


def _text(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, "").strip() or default


def _number(name: str, default: float | None = None) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None


def _choice(name: str, allowed: tuple[str, ...]) -> str:
    """One of `allowed`; the first is the default."""
    value = _text(name, allowed[0]).lower()
    if value not in allowed:
        raise ConfigError(f"{name} must be one of {', '.join(allowed)}, got {value!r}")
    return value


# Each vendor's own model and voice settings, read in load_settings().
VENDOR_SETTINGS = (
    "SARVAM_STT_MODEL", "SARVAM_STT_LANGUAGE", "SARVAM_STT_MODE",
    "ELEVENLABS_STT_MODEL", "ELEVENLABS_STT_LANGUAGE",
    "SARVAM_LLM_MODEL", "OPENAI_LLM_MODEL",
    "SARVAM_TTS_MODEL", "SARVAM_TTS_SPEAKER", "SARVAM_TTS_LANGUAGE",
    "SARVAM_TTS_SAMPLE_RATE", "SARVAM_TTS_CODEC",
    "ELEVENLABS_TTS_MODEL", "ELEVENLABS_TTS_VOICE", "ELEVENLABS_TTS_LANGUAGE",
    "ELEVENLABS_TTS_CODEC",
)

# Settings that used to be shared by every vendor. Each vendor now has its
# own, so an old .env would be silently ignored: refuse it instead.
_SPLIT_PER_VENDOR = {
    "STT_MODEL": "SARVAM_STT_MODEL / ELEVENLABS_STT_MODEL",
    "STT_LANGUAGE": "SARVAM_STT_LANGUAGE / ELEVENLABS_STT_LANGUAGE",
    "STT_MODE": "SARVAM_STT_MODE",
    "LLM_MODEL": "SARVAM_LLM_MODEL / OPENAI_LLM_MODEL",
    "TTS_MODEL": "SARVAM_TTS_MODEL / ELEVENLABS_TTS_MODEL",
    "TTS_SPEAKER": "SARVAM_TTS_SPEAKER / ELEVENLABS_TTS_VOICE",
    "TTS_LANGUAGE": "SARVAM_TTS_LANGUAGE / ELEVENLABS_TTS_LANGUAGE",
    "TTS_SAMPLE_RATE": "SARVAM_TTS_SAMPLE_RATE",
    "TTS_CODEC": "SARVAM_TTS_CODEC / ELEVENLABS_TTS_CODEC",
}


def _refuse_shared_vendor_settings() -> None:
    old = [name for name in _SPLIT_PER_VENDOR if _text(name)]
    if old:
        raise ConfigError(
            "settings are now per vendor; rename in .env: "
            + ", ".join(f"{name} -> {_SPLIT_PER_VENDOR[name]}" for name in old)
        )


def load_settings() -> Settings:
    """Read .env and the environment into a Settings object.

    Each vendor has its own model and voice settings, so switching the stack
    is only the *_PROVIDER lines. Left blank they stay None, and that
    vendor's builder fills in its own default. API keys are checked by the
    builder that needs them; main.py builds every provider at startup, so a
    missing key is still a startup error rather than a caller hearing silence.
    """
    load_dotenv()
    _refuse_shared_vendor_settings()

    tts_rate = _number("SARVAM_TTS_SAMPLE_RATE")
    return Settings(
        sarvam_api_key=_text("SARVAM_API_KEY", ""),
        openai_api_key=_text("OPENAI_API_KEY", ""),
        elevenlabs_api_key=_text("ELEVENLABS_API_KEY", ""),
        # Sarvam is the production stack, so it is the default for all three.
        stt_provider=_text("STT_PROVIDER", "sarvam"),
        llm_provider=_text("LLM_PROVIDER", "sarvam"),
        tts_provider=_text("TTS_PROVIDER", "sarvam"),
        stt_sample_rate=int(_number("STT_SAMPLE_RATE", 16000)),
        sarvam_stt_model=_text("SARVAM_STT_MODEL"),
        sarvam_stt_language=_text("SARVAM_STT_LANGUAGE"),
        sarvam_stt_mode=_text("SARVAM_STT_MODE", "transcribe"),
        elevenlabs_stt_model=_text("ELEVENLABS_STT_MODEL"),
        elevenlabs_stt_language=_text("ELEVENLABS_STT_LANGUAGE"),
        sarvam_llm_model=_text("SARVAM_LLM_MODEL"),
        openai_llm_model=_text("OPENAI_LLM_MODEL"),
        sarvam_tts_model=_text("SARVAM_TTS_MODEL"),
        sarvam_tts_speaker=_text("SARVAM_TTS_SPEAKER"),
        sarvam_tts_language=_text("SARVAM_TTS_LANGUAGE"),
        sarvam_tts_sample_rate=int(tts_rate) if tts_rate is not None else None,
        sarvam_tts_codec=_text("SARVAM_TTS_CODEC"),
        elevenlabs_tts_model=_text("ELEVENLABS_TTS_MODEL"),
        elevenlabs_tts_voice=_text("ELEVENLABS_TTS_VOICE"),
        elevenlabs_tts_language=_text("ELEVENLABS_TTS_LANGUAGE"),
        elevenlabs_tts_codec=_text("ELEVENLABS_TTS_CODEC"),
        min_endpointing_delay=_number("MIN_ENDPOINTING_DELAY", 0.2),
        max_call_minutes=_number("MAX_CALL_MINUTES", 10),
        dashboard_login=_choice("DASHBOARD_LOGIN", ("google", "off")),
        admin_emails=frozenset(
            e.strip().lower() for e in (_text("ADMIN_EMAILS") or "").split(",") if e.strip()
        ),
        dashboard_url=_text("DASHBOARD_URL", "http://localhost:3000").rstrip("/"),
        session_secret=_text("SESSION_SECRET", ""),
        google_client_id=_text("GOOGLE_CLIENT_ID", ""),
        google_client_secret=_text("GOOGLE_CLIENT_SECRET", ""),
        database_url=_text("DATABASE_URL", "sqlite:///data/clinic.db"),
        livekit_url=_text("LIVEKIT_URL", ""),
        livekit_api_key=_text("LIVEKIT_API_KEY", ""),
        livekit_api_secret=_text("LIVEKIT_API_SECRET", ""),
        public_base_url=_text("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/"),
        api_host=_text("API_HOST", "127.0.0.1"),
        api_port=int(_number("API_PORT", 8080)),
        client_ip_header=_text("CLIENT_IP_HEADER"),
    )
