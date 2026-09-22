"""main.py must refuse to start with a bad config, in one line, before the worker."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def seeded_db(tmp_path) -> str:
    from clinic_agent.store import migrations
    from clinic_agent.store.db import make_engine, session_factory
    from seeds.demo_clinic import seed_demo

    url = f"sqlite:///{tmp_path}/boot.db"
    engine = make_engine(url)
    migrations.upgrade(engine)
    with session_factory(engine)() as s:
        seed_demo(s)
    return url


def run_main(tmp_path, *args, **overrides):
    # load_dotenv searches upward from config.py's own folder, so the code is
    # copied out of the repo; otherwise the developer's real .env is found.
    env = {k: v for k, v in os.environ.items() if not k.endswith(("_PROVIDER", "DATABASE_URL"))}
    env.pop("SARVAM_API_KEY", None)
    env.update(overrides)
    shutil.copy(BACKEND / "main.py", tmp_path)
    shutil.copytree(BACKEND / "clinic_agent", tmp_path / "clinic_agent")
    return subprocess.run(
        [sys.executable, "main.py", *(args or ("--help",))],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )


def test_missing_key_exits_with_one_line(tmp_path):
    r = run_main(tmp_path)
    assert r.returncode == 1
    assert r.stderr.strip() == (
        "configuration error: SARVAM_API_KEY is not set. "
        "Copy .env.example to .env and fill it in."
    )


def test_unknown_provider_exits_with_one_line(tmp_path):
    r = run_main(tmp_path, SARVAM_API_KEY="x", TTS_PROVIDER="eleven")
    assert r.returncode == 1
    assert r.stderr.strip() == (
        "configuration error: unknown TTS provider 'eleven'; available: ['elevenlabs', 'sarvam']"
    )


def test_unmigrated_database_exits_with_one_line(tmp_path):
    r = run_main(tmp_path, SARVAM_API_KEY="x", DATABASE_URL=f"sqlite:///{tmp_path}/none.db")
    assert r.returncode == 1
    assert r.stderr.strip().startswith("configuration error: database schema is not set up")
    assert "python -m clinic_agent.store.migrations" in r.stderr


def _two_clinics(tmp_path) -> str:
    from clinic_agent.store import repo
    from clinic_agent.store.db import make_engine, session_factory

    url = seeded_db(tmp_path)
    with session_factory(make_engine(url))() as s:
        repo.create_clinic(s, name="Cure Dental Clinic")
    return url


def test_console_with_no_clinics_says_how_to_make_one(tmp_path):
    from clinic_agent.store import migrations
    from clinic_agent.store.db import make_engine

    migrations.upgrade(make_engine(f"sqlite:///{tmp_path}/empty.db"))
    r = run_main(tmp_path, "console", "--help", SARVAM_API_KEY="x", DATABASE_URL=f"sqlite:///{tmp_path}/empty.db")
    assert r.returncode == 1
    assert r.stderr.strip().startswith("configuration error: no clinics in sqlite:///")
    assert "seeds.demo_clinic" in r.stderr


def test_console_with_several_clinics_asks_which(tmp_path):
    r = run_main(tmp_path, "console", "--help", SARVAM_API_KEY="x", DATABASE_URL=_two_clinics(tmp_path))
    assert r.returncode == 1
    assert r.stderr.strip() == (
        "configuration error: several clinics, pick one with --clinic <id> "
        "(1 = Demo Family Clinic, 2 = Cure Dental Clinic)"
    )


def test_console_clinic_flag_picks_one(tmp_path):
    r = run_main(tmp_path, "console", "--clinic", "2", "--help", SARVAM_API_KEY="x", DATABASE_URL=_two_clinics(tmp_path))
    assert r.returncode == 0, r.stderr


def test_console_unknown_clinic_exits_with_one_line(tmp_path):
    r = run_main(tmp_path, "console", "--clinic=9", "--help", SARVAM_API_KEY="x", DATABASE_URL=seeded_db(tmp_path))
    assert r.returncode == 1
    assert r.stderr.strip() == "configuration error: no clinic with id 9"


def test_clinic_flag_is_console_only(tmp_path):
    # dev and start calls run in child processes and must name their clinic.
    r = run_main(tmp_path, "start", "--clinic", "1", SARVAM_API_KEY="x", DATABASE_URL=seeded_db(tmp_path))
    assert r.returncode == 1
    assert "--clinic is for console only" in r.stderr


def test_valid_config_reaches_the_cli(tmp_path):
    r = run_main(tmp_path, SARVAM_API_KEY="x", DATABASE_URL=seeded_db(tmp_path))
    assert r.returncode == 0
    assert "console" in r.stdout and "dev" in r.stdout and "start" in r.stdout


def test_text_mode_needs_no_speech_keys(tmp_path):
    # LLM key only: no Sarvam key for STT, no ElevenLabs key for TTS.
    r = run_main(
        tmp_path, "console", "--text", "--help",
        LLM_PROVIDER="openai", OPENAI_API_KEY="sk-x", TTS_PROVIDER="elevenlabs",
        DATABASE_URL=seeded_db(tmp_path),
    )
    assert r.returncode == 0, r.stderr
    assert "text mode" in r.stdout


def test_voice_console_still_needs_speech_keys(tmp_path):
    r = run_main(
        tmp_path, "console", "--help",
        LLM_PROVIDER="openai", OPENAI_API_KEY="sk-x", TTS_PROVIDER="elevenlabs",
        DATABASE_URL=seeded_db(tmp_path),
    )
    assert r.returncode == 1
    assert "SARVAM_API_KEY is not set" in r.stderr
