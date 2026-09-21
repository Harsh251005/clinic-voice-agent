from datetime import date, datetime, time

import pytest

from clinic_agent import booking
from clinic_agent.booking import BookingError
from clinic_agent.store import repo

NOW = datetime(2026, 9, 21, 9, 0)  # Monday morning
TUE = date(2026, 9, 22)


def find(db, day=TUE, **kw):
    s, clinic_id = db
    return booking.find_slots(s, clinic_id, day, NOW, **kw)


def book(db, doctor="Asha", day=TUE, at=time(10, 0), name="Ravi", phone="98765 43210"):
    s, clinic_id = db
    return booking.book_slot(s, clinic_id, doctor, day, at, name, phone, NOW)


# ---------- phone and doctor matching ----------

@pytest.mark.parametrize("raw", ["9876543210", "98765 43210", "+91 98765-43210", "09876543210"])
def test_phone_formats_normalise(raw):
    assert booking.normalise_phone(raw) == "9876543210"


@pytest.mark.parametrize("raw", ["12345", "5876543210", "98765432101"])
def test_bad_phone_is_refused(raw):
    with pytest.raises(BookingError, match="not a valid 10-digit mobile"):
        booking.normalise_phone(raw)


@pytest.mark.parametrize("spoken", ["Dr. Asha Mehta", "asha mehta", "Doctor Asha", "Mehta"])
def test_doctor_names_resolve(db, spoken):
    s, clinic_id = db
    assert booking.resolve_doctor(repo.get_clinic(s, clinic_id), spoken).name == "Dr. Asha Mehta"


def test_unknown_doctor_lists_who_exists(db):
    s, clinic_id = db
    with pytest.raises(BookingError, match="Doctors: Dr. Asha Mehta, Dr. Rohan Iyer"):
        booking.resolve_doctor(repo.get_clinic(s, clinic_id), "Dr. Sharma")


def test_ambiguous_name_asks_which(db):
    s, clinic_id = db
    repo.add_doctor(s, clinic_id, name="Dr. Vikram Mehta")
    s.expire_all()
    with pytest.raises(BookingError, match="'Mehta' matches more than one doctor"):
        booking.resolve_doctor(repo.get_clinic(s, clinic_id), "Mehta")


def test_inactive_doctor_is_not_bookable(db):
    s, clinic_id = db
    rohan = repo.get_clinic(s, clinic_id).doctors[1]
    repo.update_doctor(s, rohan.id, active=False)
    s.expire_all()
    with pytest.raises(BookingError, match="No doctor called"):
        booking.resolve_doctor(repo.get_clinic(s, clinic_id), "Rohan")


# ---------- finding slots ----------

def test_finds_the_first_slots_per_doctor(db):
    out = find(db)
    assert "Dr. Asha Mehta on Tuesday 22 September 2026: 10:00, 10:15, 10:30." in out
    # Rohan doesn't sit on Tuesdays: says why and the next free day
    assert "Dr. Rohan Iyer on Tuesday 22 September 2026: none - doctor does not sit on Tuesdays." in out
    assert "Next free: Wednesday 23 September 2026, 11:00, 11:20, 11:40." in out


def test_part_of_day_and_one_doctor(db):
    assert find(db, doctor_name="Asha", part_of_day="evening") == (
        "Dr. Asha Mehta on Tuesday 22 September 2026: 17:00, 17:15, 17:30."
    )


def test_slots_offered_follows_clinic_setting(db):
    s, clinic_id = db
    repo.update_clinic(s, clinic_id, slots_offered=2)
    assert find(db, doctor_name="Asha").endswith("10:00, 10:15.")


def test_booked_slot_is_not_offered(db):
    book(db)
    assert "10:15, 10:30, 10:45" in find(db, doctor_name="Asha")


def test_clinic_holiday_gives_reason_and_next_day(db):
    s, clinic_id = db
    repo.add_time_off(s, clinic_id, TUE, TUE, reason="Ganesh Chaturthi")
    out = find(db, doctor_name="Asha")
    assert "none - clinic closed (Ganesh Chaturthi)" in out
    assert "Next free: Wednesday 23 September 2026" in out


def test_doctor_leave(db):
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    repo.add_time_off(s, clinic_id, TUE, date(2026, 9, 23), doctor_id=asha.id)
    out = find(db, doctor_name="Asha")
    assert "none - doctor on leave" in out and "Next free: Thursday 24 September 2026" in out


def test_past_and_far_future_days_are_refused(db):
    with pytest.raises(BookingError, match="in the past"):
        find(db, day=date(2026, 9, 20))
    with pytest.raises(BookingError, match="30 days ahead"):
        find(db, day=date(2026, 11, 30))


def test_today_skips_times_already_gone(db):
    # 09:00 now, 30-minute lead: 10:00 is fine, and nothing before it exists anyway
    s, clinic_id = db
    late = datetime(2026, 9, 21, 10, 50)
    out = booking.find_slots(s, clinic_id, date(2026, 9, 21), late, doctor_name="Asha")
    assert out.endswith("11:30, 11:45, 12:00.")


# ---------- booking ----------

def test_booking_succeeds_and_is_stored(db):
    out = book(db)
    assert out.startswith("Booked, appointment number ")
    assert "Dr. Asha Mehta, Tuesday 22 September 2026 at 10:00, for Ravi, mobile 9876543210." in out
    s, clinic_id = db
    (appt,) = repo.appointments_on(s, clinic_id, TUE)
    assert appt.source == "voice" and appt.patient.phone == "9876543210"


def test_booking_a_taken_slot_offers_others(db):
    book(db)
    with pytest.raises(BookingError, match=r"not free at 10:00.*Free times that day: 10:15, 10:30, 10:45"):
        book(db, name="Sunita", phone="9123456780")


def test_booking_outside_hours_is_refused(db):
    with pytest.raises(BookingError, match="not free at 14:00"):
        book(db, at=time(14, 0))


def test_booking_off_grid_time_is_refused(db):
    with pytest.raises(BookingError, match="not free at 10:05"):
        book(db, at=time(10, 5))


def test_race_between_check_and_insert_is_caught(db, monkeypatch):
    # Another caller books the same slot after our free-check but before our insert.
    s, clinic_id = db
    real_book = repo.book

    def sneaky(*args, **kwargs):
        real_book(s, clinic_id, args[2], args[3], "Other", "9000000009")
        return real_book(*args, **kwargs)

    monkeypatch.setattr(repo, "book", sneaky)
    with pytest.raises(BookingError, match="just taken by another caller. Offer: 10:15"):
        book(db)


def test_missing_name_and_bad_phone(db):
    with pytest.raises(BookingError, match="name is missing"):
        book(db, name="  ")
    with pytest.raises(BookingError, match="not a valid 10-digit"):
        book(db, phone="12345")
