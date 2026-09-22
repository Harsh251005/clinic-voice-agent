import os

import pytest

from clinic_agent import config

SETTING_NAMES = [
    "SARVAM_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY", "STT_PROVIDER", "LLM_PROVIDER", "TTS_PROVIDER",
    "STT_MODEL", "STT_LANGUAGE", "STT_MODE", "STT_SAMPLE_RATE", "LLM_MODEL",
    "TTS_MODEL", "TTS_SPEAKER", "TTS_LANGUAGE", "TTS_SAMPLE_RATE", "TTS_CODEC",
    "MIN_ENDPOINTING_DELAY", "DATABASE_URL", "PUBLIC_BASE_URL",
    "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "API_HOST", "API_PORT", "CLIENT_IP_HEADER",
]


@pytest.fixture
def env(monkeypatch):
    """A clean environment that ignores the developer's real .env file."""
    for name in SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    return monkeypatch


# Set to run every `db` test against Postgres as well as SQLite, e.g.
#   TEST_POSTGRES_URL=postgresql+psycopg://clinic:clinic-dev@127.0.0.1:5433/clinic_test
# The database is wiped before each test: never point it at real data.
POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", "").strip()


@pytest.fixture(params=["sqlite", "postgres"] if POSTGRES_URL else ["sqlite"])
def db(request):
    """A fresh database with the demo clinic. Yields (session, clinic_id)."""
    from clinic_agent.store import migrations
    from clinic_agent.store.db import make_engine, session_factory
    from seeds.demo_clinic import seed_demo

    if request.param == "postgres":
        if request.node.get_closest_marker("live"):
            pytest.skip("live evals grade the LLM, not the database: SQLite is enough")
        engine = make_engine(POSTGRES_URL)
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    else:
        engine = make_engine("sqlite:///:memory:")
    migrations.upgrade(engine)
    with session_factory(engine)() as s:
        yield s, seed_demo(s)
    engine.dispose()
