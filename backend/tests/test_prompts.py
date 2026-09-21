from datetime import date, datetime

from clinic_agent.prompts import build_instructions, weekly_hours
from clinic_agent.store import repo

NOW = datetime(2026, 9, 21, 15, 30)  # Monday afternoon


def test_facts_come_from_the_database(db):
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW)
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
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW)
    assert "Dr. Rohan Iyer" not in text


def test_leave_and_holidays_are_listed(db):
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    off = [
        repo.add_time_off(s, clinic_id, date(2026, 10, 2), date(2026, 10, 2), reason="Gandhi Jayanti"),
        repo.add_time_off(s, clinic_id, date(2026, 10, 5), date(2026, 10, 9), doctor_id=asha.id),
    ]
    text = build_instructions(repo.get_clinic(s, clinic_id), off, NOW)
    assert "Whole clinic closed: Friday 02 October (Gandhi Jayanti)" in text
    assert "Dr. Asha Mehta on leave: 05 October to 09 October" in text


def test_doctor_without_hours(db):
    s, clinic_id = db
    doc = repo.add_doctor(s, clinic_id, name="Dr. New")
    assert weekly_hours(doc) == "no regular hours set"


def test_prompt_describes_booking_and_only_built_capabilities(db):
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW)
    assert "find_available_slots" in text and "book_appointment" in text
    assert "only after a clear yes" in text
    assert "book, cancel and move appointments" in text
    assert "find_my_appointments" in text and "reschedule_appointment" in text
    assert "call end_call" in text


def test_unknown_doctor_rule(db):
    s, clinic_id = db
    text = build_instructions(repo.get_clinic(s, clinic_id), [], NOW)
    assert "Never answer about one\n  doctor as if they were another" in text
