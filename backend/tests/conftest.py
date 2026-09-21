import pytest

from clinic_agent import config

SETTING_NAMES = [
    "SARVAM_API_KEY", "STT_PROVIDER", "LLM_PROVIDER", "TTS_PROVIDER",
    "STT_MODEL", "STT_LANGUAGE", "STT_MODE", "STT_SAMPLE_RATE", "LLM_MODEL",
    "TTS_MODEL", "TTS_SPEAKER", "TTS_LANGUAGE", "TTS_SAMPLE_RATE", "TTS_CODEC",
    "MIN_ENDPOINTING_DELAY",
]


@pytest.fixture
def env(monkeypatch):
    """A clean environment that ignores the developer's real .env file."""
    for name in SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    return monkeypatch
