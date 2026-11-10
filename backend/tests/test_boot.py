"""main.py must refuse to start with a bad config, in one line, before the worker."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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
    env = {k: v for k, v in os.environ.items() if not k.endswith(("_PROVIDER", "DATABASE_URL", "_API_KEY"))}
    env.update(overrides)
    shutil.copy(BACKEND / "main.py", tmp_path)
    shutil.copytree(BACKEND / "clinic_agent", tmp_path / "clinic_agent")
    return subprocess.run(
        [sys.executable, "main.py", *(args or ("--help",))],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )


def test_the_hindi_line_without_its_key_exits_with_one_line(tmp_path):
    r = run_main(tmp_path, DATABASE_URL=seeded_db(tmp_path))
    assert r.returncode == 1
    assert r.stderr.strip() == "configuration error: no language line can take calls: Hindi: " \
        "SARVAM_API_KEY is not set. Copy .env.example to .env and fill it in."


def openai_brain_db(tmp_path) -> str:
    """The brain is chosen in the dashboard now (Admin > Receptionist), not .env."""
    from clinic_agent.store import repo
    from clinic_agent.store.db import make_engine, session_factory

    url = seeded_db(tmp_path)
    with session_factory(make_engine(url))() as s:
        repo.update_system_settings(s, hindi_llm="openai")
    return url


def test_an_openai_brain_without_its_key_exits_with_one_line(tmp_path):
    r = run_main(tmp_path, SARVAM_API_KEY="x", DATABASE_URL=openai_brain_db(tmp_path))
    assert r.returncode == 1
    assert "Hindi: OPENAI_API_KEY is not set" in r.stderr.strip()
    (again := tmp_path / "with-key").mkdir()
    r = run_main(again, SARVAM_API_KEY="x", OPENAI_API_KEY="sk-x", DATABASE_URL=openai_brain_db(again))
    assert r.returncode == 0, r.stderr
    assert "warning" not in r.stderr


def test_a_retired_vendor_switch_exits_with_one_line(tmp_path):
    r = run_main(tmp_path, SARVAM_API_KEY="x", TTS_PROVIDER="sarvam")
    assert r.returncode == 1
    assert r.stderr.strip().startswith("configuration error: remove from .env: TTS_PROVIDER (calls run on the Hindi line")


def test_a_leftover_key_of_the_removed_vendor_exits_with_one_line(tmp_path):
    r = run_main(tmp_path, SARVAM_API_KEY="x", ELEVENLABS_API_KEY="old", DATABASE_URL=seeded_db(tmp_path))
    assert r.returncode == 1
    assert r.stderr.strip().startswith("configuration error: remove from .env: ELEVENLABS_API_KEY")


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


@pytest.mark.parametrize("flag", [["--language", "en"], ["--language=hi"]])
def test_the_language_flag_is_gone(tmp_path, flag):
    # Every call is in Hindi (2026-11-08): a leftover flag is named, not passed to LiveKit's CLI.
    r = run_main(tmp_path, "console", *flag, "--help", SARVAM_API_KEY="x", DATABASE_URL=seeded_db(tmp_path))
    assert r.returncode == 1
    assert r.stderr.strip() == "configuration error: --language is gone: every call is in Hindi (the only line)"


def test_valid_config_reaches_the_cli(tmp_path):
    r = run_main(tmp_path, SARVAM_API_KEY="x", DATABASE_URL=seeded_db(tmp_path))
    assert r.returncode == 0
    assert "console" in r.stdout and "dev" in r.stdout and "start" in r.stdout


def test_text_mode_needs_no_speech_keys(tmp_path):
    # The brain's key only: no Sarvam key for the ears or voice.
    r = run_main(
        tmp_path, "console", "--text", "--help",
        OPENAI_API_KEY="sk-x", DATABASE_URL=openai_brain_db(tmp_path),
    )
    assert r.returncode == 0, r.stderr
    assert "text mode" in r.stdout


def test_voice_console_without_the_speech_key_exits_with_one_line(tmp_path):
    r = run_main(
        tmp_path, "console", "--help",
        OPENAI_API_KEY="sk-x", DATABASE_URL=openai_brain_db(tmp_path),
    )
    assert r.returncode == 1
    assert r.stderr.strip().startswith("configuration error: no language line can take calls: Hindi: SARVAM_API_KEY is not set")


def test_a_setting_moved_to_the_dashboard_left_in_env_exits_with_one_line(tmp_path):
    # Harsh, 2026-11-10: those settings live in the database; a leftover line would be silently ignored.
    r = run_main(tmp_path, SARVAM_API_KEY="x", HINDI_LLM="openai", SARVAM_TTS_PACE="0.95",
                 DATABASE_URL=seeded_db(tmp_path))
    assert r.returncode == 1
    assert r.stderr.strip().startswith("configuration error: these settings are now set in the dashboard")
    assert "delete them from .env: HINDI_LLM, SARVAM_TTS_PACE." in r.stderr
