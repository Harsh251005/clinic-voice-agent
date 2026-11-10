"""The receptionist's settings in the database (Harsh, 2026-11-10): what
every clinic shares, what each clinic sets, the checks on save, and the
one-time copy of the old .env lines."""

import pytest

from clinic_agent import receptionist_settings as rs
from clinic_agent.store import repo


def test_a_new_database_has_the_codes_defaults(db):
    s, clinic_id = db
    row = repo.system_settings(s)
    for f in rs.SYSTEM:
        assert getattr(row, f.name) == f.default, f.name
    clinic = repo.get_clinic(s, clinic_id)
    for f in rs.CLINIC:
        assert getattr(clinic, f.name) == f.default, f.name


def test_settings_are_checked_on_save(db):
    s, clinic_id = db
    repo.update_system_settings(s, hindi_llm="OpenAI", interrupt_min_speech="0.4", greeting_interruptible=True)
    row = repo.system_settings(s)
    assert (row.hindi_llm, row.interrupt_min_speech, row.greeting_interruptible) == ("openai", 0.4, True)
    with pytest.raises(ValueError, match="one of: sarvam, openai"):
        repo.update_system_settings(s, hindi_llm="gemini")  # never a vendor outside the allowed ones
    with pytest.raises(ValueError, match="at most 500"):
        repo.update_system_settings(s, rules="word " * 501)
    with pytest.raises(ValueError, match="between 0.5 and 2"):
        repo.update_clinic_receptionist(s, clinic_id, tts_pace=2.5)
    with pytest.raises(ValueError, match="at most 150"):
        repo.update_clinic_receptionist(s, clinic_id, instructions="word " * 151)
    repo.update_clinic_receptionist(s, clinic_id, tts_pitch="", directions="  Opposite the station  ")
    clinic = repo.get_clinic(s, clinic_id)
    assert clinic.tts_pitch is None and clinic.directions == "Opposite the station"
    with pytest.raises(KeyError):
        repo.update_clinic_receptionist(s, clinic_id, name="renamed")  # not a receptionist setting


def test_old_env_lines_are_copied_in_once(db):
    s, clinic_id = db
    repo.create_clinic(s, name="Second Clinic")
    env = {"HINDI_LLM": "openai", "SARVAM_TTS_PACE": "0.95", "SARVAM_TTS_SPEAKER": "aparna_hi_customer",
           "MIN_ENDPOINTING_DELAY": "0.3"}
    copied = repo.copy_settings_from_env(s, env)
    assert sorted(copied) == sorted(env)
    row = repo.system_settings(s)
    assert (row.hindi_llm, row.min_endpointing_delay) == ("openai", 0.3)
    for clinic in repo.list_clinics(s):  # a clinic's setting goes to every clinic
        assert (clinic.tts_pace, clinic.tts_speaker) == (0.95, "aparna_hi_customer")
    repo.update_system_settings(s, hindi_llm="sarvam")  # the admin changes it afterwards
    assert repo.copy_settings_from_env(s, env) == []  # never copied again
    assert repo.system_settings(s).hindi_llm == "sarvam"


def test_every_moved_line_names_a_real_setting():
    from clinic_agent.config import VENDOR_SETTINGS

    known = set(VENDOR_SETTINGS) | {"HINDI_LLM", "MIN_ENDPOINTING_DELAY", "NUMBER_ENDPOINTING_DELAY",
                                     "INTERRUPT_MIN_SPEECH", "VAD_MIN_SILENCE", "MAX_CALL_MINUTES"}
    assert set(rs.MOVED_ENV) <= known
