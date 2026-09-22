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

    # --- speech to text (None = the selected provider's default) ---
    stt_model: str | None
    stt_language: str | None
    stt_mode: str  # Sarvam only
    stt_sample_rate: int

    # --- language model (None = the selected provider's default) ---
    llm_model: str | None

    # --- text to speech (None = the selected provider's default) ---
    tts_model: str | None
    tts_speaker: str | None
    tts_language: str | None
    tts_sample_rate: int | None
    tts_codec: str | None

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


def load_settings() -> Settings:
    """Read .env and the environment into a Settings object.

    Model and voice settings left blank stay None, and the selected
    provider's builder fills in its own default. API keys are checked by the
    builder that needs them; main.py builds every provider at startup, so a
    missing key is still a startup error rather than a caller hearing silence.
    """
    load_dotenv()

    tts_rate = _number("TTS_SAMPLE_RATE")
    return Settings(
        sarvam_api_key=_text("SARVAM_API_KEY", ""),
        openai_api_key=_text("OPENAI_API_KEY", ""),
        elevenlabs_api_key=_text("ELEVENLABS_API_KEY", ""),
        # Sarvam is the production stack, so it is the default for all three.
        stt_provider=_text("STT_PROVIDER", "sarvam"),
        llm_provider=_text("LLM_PROVIDER", "sarvam"),
        tts_provider=_text("TTS_PROVIDER", "sarvam"),
        stt_model=_text("STT_MODEL"),
        stt_language=_text("STT_LANGUAGE"),
        stt_mode=_text("STT_MODE", "transcribe"),
        stt_sample_rate=int(_number("STT_SAMPLE_RATE", 16000)),
        llm_model=_text("LLM_MODEL"),
        tts_model=_text("TTS_MODEL"),
        tts_speaker=_text("TTS_SPEAKER"),
        tts_language=_text("TTS_LANGUAGE"),
        tts_sample_rate=int(tts_rate) if tts_rate is not None else None,
        tts_codec=_text("TTS_CODEC"),
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
