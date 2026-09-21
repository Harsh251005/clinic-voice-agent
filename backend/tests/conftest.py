import pytest

from clinic_agent import config

SETTING_NAMES = [
    "SARVAM_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY", "STT_PROVIDER", "LLM_PROVIDER", "TTS_PROVIDER",
    "STT_MODEL", "STT_LANGUAGE", "STT_MODE", "STT_SAMPLE_RATE", "LLM_MODEL",
    "TTS_MODEL", "TTS_SPEAKER", "TTS_LANGUAGE", "TTS_SAMPLE_RATE", "TTS_CODEC",
    "MIN_ENDPOINTING_DELAY", "DATABASE_URL", "CLINIC_ID",
]


@pytest.fixture
def env(monkeypatch):
    """A clean environment that ignores the developer's real .env file."""
    for name in SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    return monkeypatch


@pytest.fixture
def db():
    """A fresh in-memory database with the demo clinic. Yields (session, clinic_id)."""
    from clinic_agent.store.db import init_db, make_engine, session_factory
    from seeds.demo_clinic import seed_demo

    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    with session_factory(engine)() as s:
        yield s, seed_demo(s)
