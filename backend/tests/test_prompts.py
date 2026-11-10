import re
from datetime import date, datetime

import pytest

from clinic_agent.prompts import build_instructions, weekly_hours
from clinic_agent.store import repo

NOW = datetime(2026, 9, 21, 15, 30)  # Monday afternoon


def test_facts_come_from_the_database(db):
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    assert "receptionist of Demo Family Clinic" in text
    assert "Shop 4, Sunrise Apartments, Borivali East, Mumbai" in text
    assert "Dr. Asha Mehta (General Physician, fee ₹500)" in text
    assert "Q: Is there parking? A: Two-wheeler parking only" in text
    assert "Monday, 21 September 2026, 15:30" in text


def test_hours_group_consecutive_days_and_show_split_shifts(db):
    s, clinic_id = db
    asha, rohan = repo.get_clinic(s, clinic_id).doctors
    assert weekly_hours(asha) == (
        "Monday to Saturday 10:00-13:00 and 17:00-20:00; Sunday not available"
    )
    assert weekly_hours(rohan) == (
        "Monday 11:00-14:00; Tuesday not available; Wednesday 11:00-14:00; "
        "Thursday not available; Friday 11:00-14:00; Saturday to Sunday not available"
    )


def test_inactive_doctor_is_left_out(db):
    s, clinic_id = db
    rohan = repo.get_clinic(s, clinic_id).doctors[1]
    repo.update_doctor(s, rohan.id, active=False)
    s.expire_all()
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    assert "Dr. Rohan Iyer" not in text


def test_leave_and_holidays_are_listed(db):
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    off = [
        repo.add_time_off(s, clinic_id, date(2026, 10, 2), date(2026, 10, 2), reason="Gandhi Jayanti"),
        repo.add_time_off(s, clinic_id, date(2026, 10, 5), date(2026, 10, 9), doctor_id=asha.id),
    ]
    text = build_instructions(repo.get_clinic(s, clinic_id), off, NOW, "hi")
    assert "Whole clinic closed: Friday 02 October (Gandhi Jayanti)" in text
    assert "Dr. Asha Mehta on leave: 05 October to 09 October" in text


def test_doctor_without_hours(db):
    s, clinic_id = db
    doc = repo.add_doctor(s, clinic_id, name="Dr. New")
    assert weekly_hours(doc) == "no regular hours set"


def test_prompt_describes_booking_and_only_built_capabilities(db):
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    assert "find_available_slots" in text and "book_appointment" in text
    assert "Only after a clear yes, call book_appointment" in text
    assert "book, cancel and move appointments" in text
    assert "find_my_appointments" in text and "reschedule_appointment" in text
    assert "call end_call" in text


def test_the_receptionist_speaks_as_a_woman(db):
    # Every voice is female; masculine Hindi ("बात कर रहा हूँ") from a woman's
    # voice sounds wrong to every caller.
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    assert "You are an automated assistant and a woman" in text
    assert 'About yourself always feminine ("मैं देखती हूँ", "बताती हूँ")' in text
    assert 'never "sir" or "madam"' in text  # the caller's gender is never assumed


def test_unknown_doctor_rule(db):
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    assert "A doctor not in CLINIC FACTS is not at this clinic: say who is" in text


def test_the_only_doctor_is_never_asked_about(db):
    # Seen 2026-10-24: a clinic with one doctor, and the agent asked "which doctor?".
    s, clinic_id = db
    two = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    assert "- Doctors (2: ask which one only if the caller hasn't said or described one):" in two
    repo.update_doctor(s, repo.get_clinic(s, clinic_id).doctors[1].id, active=False)
    s.expire_all()
    one = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    assert "the clinic's only one, so never ask which doctor" in one
    # Not "every appointment is with them": that read as "book whatever the caller says"
    # (Harsh, 2026-11-09: fever booked with an eye specialist).
    assert "every appointment" not in one


def test_the_model_knows_the_greeting_was_said_and_never_greets_again(db):
    # The greeting is fixed text said before the model speaks (voice_clips); its words are the admin's.
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    opening = text[text.index("Opening:"):text.index("Language:")]
    assert "fixed greeting, already said for you" in opening and "Never greet again" in opening


def test_visit_reason_is_asked_for_in_english():
    # The dashboard is English only: the agent speaks Hindi but files the reason in English.
    from clinic_agent.prompts import RULES

    assert "pass the reason in short English" in " ".join(RULES["hi"].split())


def test_a_reason_outside_every_specialty_is_declined_not_booked():
    # Harsh, 2026-11-09: "fever" was booked with the clinic's only doctor, an eye
    # specialist. The reason comes first and is matched to the specialties.
    rules = _rules("hi")
    assert "First ask briefly why they are coming" in rules
    right = rules[rules.index("Right doctor:"):rules.index("Cancel or move:")]
    for rule in ["match the reason to each specialty", "book nothing",
                 "suggest a type of doctor only if obvious", "never one not in CLINIC FACTS",
                 "never diagnose", "Unsure: book"]:
        assert rule in right, rule
    assert rules.index("First ask briefly why") < rules.index("find_available_slots")


def _rules(language):
    from clinic_agent.prompts import RULES

    return " ".join(RULES[language].split())


def test_the_core_rules_are_there():
    # The safety and booking rules are the core: the line must have them.
    rules = _rules("hi")
    for rule in [
        "Call check_booking", "Only after a clear yes, call book_appointment",
        "call again with the same details after a clear yes",
        "call end_call", "never give medical advice", "one-zero-eight", "one-one-two",
        "A doctor not in CLINIC FACTS is not at this clinic",
        "No messages, holds, transfers or callbacks",
    ]:
        assert rule in rules, rule


def test_the_rules_stay_short():
    # Harsh, 2026-10-24: never more than 500 words: a long prompt costs every
    # turn and the model follows a short one better.
    assert len(_rules("hi").split()) <= 500


def test_the_hindi_line_stays_hindi_and_promises_no_english_line():
    # The English line is gone (2026-11-08): never tell a caller to call back for one.
    rules = _rules("hi")
    assert "Always reply in Hindi, to the end of the call" in rules
    assert "this receptionist speaks Hindi only" in rules
    assert "never Roman letters" in rules
    assert "choose English" not in rules


def test_the_hindi_line_says_names_as_the_clinic_spelt_them(db):
    # The LLM spelt "Dharnidharka" two ways in one call (2026-10-12): staff fix it once.
    s, clinic_id = db
    clinic = repo.get_clinic(s, clinic_id)
    repo.update_clinic(s, clinic_id, name_hi="डेमो फ़ैमिली क्लिनिक")
    repo.update_doctor(s, clinic.doctors[0].id, name_hi="डॉक्टर आशा मेहता")
    clinic = repo.get_clinic(s, clinic_id)
    hindi = build_instructions(clinic, [], NOW, "hi")
    assert "- Name: Demo Family Clinic (in Hindi: डेमो फ़ैमिली क्लिनिक)" in hindi
    assert f"{clinic.doctors[0].name} (in Hindi: डॉक्टर आशा मेहता)" in hindi


def test_the_hindi_line_speaks_everyday_hindi():
    rules = _rules("hi")
    assert 'never bookish: "ज़रा", "खाली है", not "कृपया", "उपलब्ध है"' in rules
    assert 'varied acknowledgement ("जी", "अच्छा", "ठीक है")' in rules
    assert "Never repeat confirmed details" in rules
    # Harsh, 2026-11-10: replies ran ~3 sentences / 30 words; keep turns short.
    assert "Under 20 words and one question per reply, except read-backs" in rules
    assert "no dashes, brackets or lists" in rules
