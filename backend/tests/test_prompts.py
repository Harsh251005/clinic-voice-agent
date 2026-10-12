import re
from datetime import date, datetime

import pytest

from clinic_agent.prompts import build_instructions, weekly_hours
from clinic_agent.store import repo

NOW = datetime(2026, 9, 21, 15, 30)  # Monday afternoon


def test_facts_come_from_the_database(db):
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    assert "receptionist for Demo Family Clinic" in text
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
    assert "only after a clear yes" in text
    assert "book, cancel and move appointments" in text
    assert "find_my_appointments" in text and "reschedule_appointment" in text
    assert "call end_call" in text


def test_the_receptionist_speaks_as_a_woman(db):
    # Every voice is female; masculine Hindi ("बात कर रहा हूँ") from a woman's
    # voice sounds wrong to every caller.
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    assert "You are a woman" in text
    assert "मैं Demo Family Clinic की ऑटोमेटेड असिस्टेंट" in text
    assert "That is only for you" in text  # the caller is never addressed as a woman


def test_unknown_doctor_rule(db):
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    assert "Never answer about one\n  doctor as if they were another" in text


def test_the_receptionist_says_it_is_automated(db):
    # Callers must know they aren't talking to a person (the call page says it too).
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    opening = text[text.index("Opening the call:"):text.index("How you speak:")]
    assert "automated assistant" in opening and "ऑटोमेटेड असिस्टेंट" in opening


def test_the_receptionist_says_the_call_is_saved_as_text(db):
    # Every call's transcript is kept (call_record.py): callers are told, in their language.
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW, "hi")
    opening = text[text.index("Opening the call:"):text.index("How you speak:")]
    assert "saved as text for\nthe clinic's records" in opening
    assert "लिखित\nरूप में सेव होती है" in opening


def test_visit_reason_is_asked_for_in_english():
    # The dashboard is English only: the agent speaks Hindi but files the reason in English.
    from clinic_agent.prompts import RULES

    assert "always write it in short, plain English in Roman letters" in " ".join(RULES["hi"].split())
    assert "in short, plain English" in " ".join(RULES["en"].split())


def _rules(language):
    from clinic_agent.prompts import RULES

    return " ".join(RULES[language].split())


@pytest.mark.parametrize("language", ["en", "hi"])
def test_both_languages_keep_the_same_core_rules(language):
    # The safety and booking rules are the core: every line has them.
    rules = _rules(language)
    for rule in [
        "automated assistant" if language == "en" else "ऑटोमेटेड असिस्टेंट",
        "saved as text for the clinic's records",
        "call check_booking", "After a clear yes, call book_appointment", "only after a clear yes",
        "call end_call", "Do not give medical advice", "one-zero-eight", "one-one-two",
        "Never answer about one doctor as if they were another",
        "You cannot take a message, put anyone on hold",
    ]:
        assert rule in rules, rule


def test_the_english_line_speaks_only_english_and_points_to_the_hindi_line():
    rules = _rules("en")
    assert "Reply only in English" in rules and "call again and choose Hindi" in rules
    assert "Ignore the bracketed words" in rules  # the tools' Hindi time words
    # No Hindi for the English voice to read, except the one example of what the tools send.
    assert set(re.findall(r"[\u0900-\u097F]+", rules)) == {"साढ़े", "पाँच", "बजे"}


def test_the_hindi_line_stays_hindi_and_points_to_the_english_line():
    rules = _rules("hi")
    assert "the call stays in Hindi to the end" in rules and "call again and choose English" in rules
    assert "never reply in English" in rules
