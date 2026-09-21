"""Callers finding, cancelling and moving their own appointments."""

from datetime import date, datetime, time

import pytest

from clinic_agent import booking
from clinic_agent.booking import BookingError
from clinic_agent.store import repo

NOW = datetime(2026, 9, 21, 9, 0)  # Monday morning
TUE, WED = date(2026, 9, 22), date(2026, 9, 23)
PHONE = "9876543210"


@pytest.fixture
def booked(db):
    """Ravi has Tuesday 10:00 with Dr. Asha. Returns (session, clinic_id, appointment_id)."""
    s, clinic_id = db
    booking.book_slot(s, clinic_id, "Asha", TUE, time(10), "Ravi", PHONE, NOW)
    (appt,) = repo.upcoming_for_phone(s, clinic_id, PHONE, NOW)
    return s, clinic_id, appt.id


# ---------- finding ----------

def test_finds_the_callers_upcoming_appointments(booked):
    s, clinic_id, appt_id = booked
    out = booking.find_appointments(s, clinic_id, "+91 98765 43210", NOW)
    assert out == f"Appointment {appt_id}: Dr. Asha Mehta, Tuesday 22 September 2026 at 10:00, for Ravi."


def test_past_and_cancelled_appointments_are_not_listed(booked):
    s, clinic_id, appt_id = booked
    with pytest.raises(BookingError, match="No upcoming appointments"):
        booking.find_appointments(s, clinic_id, PHONE, datetime(2026, 9, 22, 11, 0))
    repo.cancel_appointment(s, appt_id)
    with pytest.raises(BookingError, match="No upcoming appointments"):
        booking.find_appointments(s, clinic_id, PHONE, NOW)


def test_unknown_number(booked):
    s, clinic_id, _ = booked
    with pytest.raises(BookingError, match="No upcoming appointments booked with mobile 9123456780"):
        booking.find_appointments(s, clinic_id, "9123456780", NOW)


# ---------- cancelling ----------

def test_cancel_frees_the_slot(booked):
    s, clinic_id, appt_id = booked
    out = booking.cancel_booking(s, clinic_id, appt_id, PHONE, NOW)
    assert out == f"Cancelled appointment {appt_id}: Dr. Asha Mehta, Tuesday 22 September 2026 at 10:00."
    assert booking.find_slots(s, clinic_id, TUE, NOW, doctor_name="Asha").endswith("10:00, 10:15, 10:30.")


def test_cannot_cancel_someone_elses_appointment(booked):
    s, clinic_id, appt_id = booked
    with pytest.raises(BookingError, match=f"No appointment {appt_id} booked with mobile 9123456780"):
        booking.cancel_booking(s, clinic_id, appt_id, "9123456780", NOW)
    assert repo.get_appointment(s, appt_id).status == "booked"


def test_unknown_and_other_clinic_ids_look_the_same(booked):
    s, clinic_id, appt_id = booked
    other = repo.create_clinic(s, name="Other Clinic")
    for cid, aid in [(clinic_id, 999), (other.id, appt_id)]:
        with pytest.raises(BookingError, match=f"No appointment {aid} booked with mobile"):
            booking.cancel_booking(s, cid, aid, PHONE, NOW)


def test_cannot_cancel_twice_or_after_it_happened(booked):
    s, clinic_id, appt_id = booked
    with pytest.raises(BookingError, match="already passed"):
        booking.cancel_booking(s, clinic_id, appt_id, PHONE, datetime(2026, 9, 22, 11, 0))
    booking.cancel_booking(s, clinic_id, appt_id, PHONE, NOW)
    with pytest.raises(BookingError, match="already cancelled"):
        booking.cancel_booking(s, clinic_id, appt_id, PHONE, NOW)


# ---------- rescheduling ----------

def test_move_keeps_the_appointment_number_and_frees_the_old_slot(booked):
    s, clinic_id, appt_id = booked
    out = booking.reschedule_booking(s, clinic_id, appt_id, PHONE, WED, time(17, 0), NOW)
    assert out == (
        f"Moved appointment {appt_id} from Dr. Asha Mehta, Tuesday 22 September 2026 at 10:00 "
        "to Dr. Asha Mehta, Wednesday 23 September 2026 at 17:00."
    )
    s.expire_all()
    moved = repo.get_appointment(s, appt_id)
    assert (moved.starts_at, moved.ends_at) == (datetime(2026, 9, 23, 17), datetime(2026, 9, 23, 17, 15))
    assert booking.find_slots(s, clinic_id, TUE, NOW, doctor_name="Asha").startswith(
        "Dr. Asha Mehta on Tuesday 22 September 2026: 10:00"
    )


def test_move_to_another_doctor_uses_their_slot_length(booked):
    s, clinic_id, appt_id = booked
    booking.reschedule_booking(s, clinic_id, appt_id, PHONE, WED, time(11, 0), NOW, doctor_name="Rohan")
    s.expire_all()
    moved = repo.get_appointment(s, appt_id)
    assert moved.doctor.name == "Dr. Rohan Iyer"
    assert moved.ends_at == datetime(2026, 9, 23, 11, 20)


def test_move_to_a_taken_time_leaves_it_unchanged(booked):
    s, clinic_id, appt_id = booked
    booking.book_slot(s, clinic_id, "Asha", WED, time(17), "Sunita", "9123456780", NOW)
    with pytest.raises(BookingError, match=r"not free at 17:00.*Free times that day: 10:00"):
        booking.reschedule_booking(s, clinic_id, appt_id, PHONE, WED, time(17, 0), NOW)
    s.expire_all()
    assert repo.get_appointment(s, appt_id).starts_at == datetime(2026, 9, 22, 10)


def test_move_race_leaves_it_unchanged(booked, monkeypatch):
    s, clinic_id, appt_id = booked
    monkeypatch.setattr(repo, "move_appointment", lambda *a: (_ for _ in ()).throw(repo.SlotTaken()))
    with pytest.raises(BookingError, match="just taken by another caller. The appointment is unchanged"):
        booking.reschedule_booking(s, clinic_id, appt_id, PHONE, WED, time(17, 0), NOW)


def test_move_to_same_time_and_to_past_day(booked):
    s, clinic_id, appt_id = booked
    with pytest.raises(BookingError, match="already at that time"):
        booking.reschedule_booking(s, clinic_id, appt_id, PHONE, TUE, time(10, 0), NOW)
    with pytest.raises(BookingError, match="in the past"):
        booking.reschedule_booking(s, clinic_id, appt_id, PHONE, date(2026, 9, 20), time(10, 0), NOW)


def test_database_refuses_moving_onto_a_booked_slot(booked):
    s, clinic_id, appt_id = booked
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    repo.book(s, clinic_id, asha.id, datetime(2026, 9, 23, 17), "Sunita", "9123456780")
    with pytest.raises(repo.SlotTaken):
        repo.move_appointment(s, appt_id, asha.id, datetime(2026, 9, 23, 17))
    s.expire_all()
    assert repo.get_appointment(s, appt_id).starts_at == datetime(2026, 9, 22, 10)
