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
    repo.update_clinic_receptionist(s, clinic_id, tts_pitch="", slots_offered="2")
    clinic = repo.get_clinic(s, clinic_id)
    assert clinic.tts_pitch is None and clinic.slots_offered == 2 and isinstance(clinic.slots_offered, int)
    for bad in (0, 7, 2.5, "two", True, None):
        with pytest.raises(ValueError, match="whole number"):
            repo.update_clinic_receptionist(s, clinic_id, slots_offered=bad)
    with pytest.raises(KeyError):
        repo.update_clinic_receptionist(s, clinic_id, directions="x")  # a clinic detail: staff set it
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


# ---------- calls read them (slice 2) ----------

def test_a_call_uses_the_dashboards_settings_over_env(db, env):
    from clinic_agent.call_settings import merge
    from clinic_agent.config import load_settings

    s, clinic_id = db
    repo.update_system_settings(s, hindi_llm="openai", openai_llm_model="gpt-4.1-mini", min_endpointing_delay=0.4,
                                greeting_interruptible=True, rules="Be kind at {clinic_name}.")
    repo.update_clinic_receptionist(s, clinic_id, tts_speaker="aparna_hi_customer", tts_pace=0.95, max_call_minutes=7)
    call = merge(load_settings(), repo.system_settings(s), repo.get_clinic(s, clinic_id))
    cfg = call.cfg
    assert (cfg.hindi_llm, cfg.openai_llm_model, cfg.min_endpointing_delay) == ("openai", "gpt-4.1-mini", 0.4)
    assert (cfg.sarvam_tts_speaker, cfg.sarvam_tts_pace, cfg.max_call_minutes) == ("aparna_hi_customer", 0.95, 7)
    assert cfg.sarvam_llm_model is None  # blank: the vendor's own default
    assert call.greeting_interruptible and call.rules == "Be kind at {clinic_name}."


def test_the_admins_rules_clinic_instructions_and_directions_reach_the_prompt(db):
    from clinic_agent.prompts import RULES, build_instructions
    from tests.test_prompts import NOW

    s, clinic_id = db
    clinic = repo.get_clinic(s, clinic_id)
    assert build_instructions(clinic, [], NOW, "hi").startswith(RULES["hi"][:20])  # blank: the code's rules
    repo.update_clinic_receptionist(s, clinic_id, instructions="Parking is free.")
    repo.update_clinic(s, clinic_id, directions="Opposite the station")
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi", rules="Rules for {clinic_name} {x}.")
    assert text.startswith(f"Rules for {clinic.name} {{x}}.")  # any braces are safe
    assert "THIS CLINIC'S OWN INSTRUCTIONS" in text and "Parking is free." in text
    assert "How to find it (when asked the way, say this, not the address word for word): Opposite the station" in text


def test_each_clinic_has_its_own_call_limit_for_dropped_calls(db):
    s, clinic_id = db
    assert repo.longest_call_minutes(s) == 10.0
    other = repo.create_clinic(s, name="Long Calls Clinic")
    repo.update_clinic_receptionist(s, other.id, max_call_minutes=25)
    assert repo.longest_call_minutes(s) == 25.0
