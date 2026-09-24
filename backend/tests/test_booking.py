from datetime import date, datetime, time, timedelta

import pytest

from clinic_agent import booking
from clinic_agent.booking import BookingError
from clinic_agent.store import repo
from conftest import plain

NOW = datetime(2026, 9, 21, 9, 0)  # Monday morning
TUE = date(2026, 9, 22)


def find(db, day=TUE, **kw):
    s, clinic_id = db
    return plain(booking.find_slots(s, clinic_id, day, NOW, **kw))


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

def every(first: str, last: str, minutes: int) -> str:
    """'10:00, 10:15, ... 11:45': what the tool lists, one time at a time."""
    t, end, out = datetime.fromisoformat(f"2026-01-01 {first}"), datetime.fromisoformat(f"2026-01-01 {last}"), []
    while t <= end:
        out.append(f"{t:%H:%M}")
        t += timedelta(minutes=minutes)
    return ", ".join(out)


ASHA_MORNING = every("10:00", "11:45", 15)
ASHA_AFTERNOON = every("12:00", "12:45", 15)
ASHA_EVENING = every("17:00", "19:45", 15)


def test_finds_every_free_time_per_doctor(db):
    out = find(db)
    assert (
        f"Dr. Asha Mehta on Tuesday 22 September 2026: free start times - morning: {ASHA_MORNING}; "
        f"afternoon: {ASHA_AFTERNOON}; evening: {ASHA_EVENING} (24 in all); suggest first 10:00, 10:15, 10:30."
    ) in out
    # Rohan doesn't sit on Tuesdays: says why and the next free day, whole
    assert "Dr. Rohan Iyer on Tuesday 22 September 2026: none - doctor does not sit on Tuesdays." in out
    assert (
        "Next free day: Wednesday 23 September 2026, free start times - morning: 11:00, 11:20, 11:40; "
        "afternoon: 12:00, 12:20, 12:40, 13:00, 13:20, 13:40 (9 in all); suggest first 11:00, 11:20, 11:40."
    ) in out


def test_later_times_are_listed_not_just_the_first_few(db):
    # The bug: only 10:00, 10:15, 10:30 reached the LLM, so "anything after
    # eleven?" or "evening?" got "nothing free".
    out = find(db, doctor_name="Asha")
    assert "11:45" in out and "19:45" in out


def test_times_are_listed_one_by_one_never_as_ranges(db):
    # The bug: "10:00 to 13:30" hid a booked 11:00 inside it, and the agent
    # offered it. Every free time is named; a booked one simply isn't there.
    book(db, at=time(11, 0))
    out = find(db, doctor_name="Asha")
    assert " to " not in out and "every" not in out
    assert "10:45, 11:15" in out


def test_each_time_carries_the_hindi_words_for_it(db):
    # Left alone the LLM said "बारह साढ़े बजे" and "सत्रह बजे".
    s, clinic_id = db
    out = booking.find_slots(s, clinic_id, TUE, NOW, doctor_name="Asha")
    assert "12:30 (साढ़े बारह बजे), 12:45 (पौने एक बजे); evening: 17:00 (पाँच बजे)" in out


def test_parts_of_the_day_are_fixed(db):
    # Morning is before 12, afternoon 12 to before 5, evening 5 on. The LLM
    # used to decide "afternoon" itself ("eleven to four").
    out = find(db, doctor_name="Asha")
    assert "morning: 10:00" in out and "11:45; afternoon: 12:00" in out and "12:45; evening: 17:00" in out
    assert find(db, doctor_name="Asha", part_of_day="afternoon").startswith(
        f"Dr. Asha Mehta on Tuesday 22 September 2026: free start times - afternoon: {ASHA_AFTERNOON} (4 in all)"
    )


def test_part_of_day_and_one_doctor(db):
    assert find(db, doctor_name="Asha", part_of_day="evening") == (
        f"Dr. Asha Mehta on Tuesday 22 September 2026: free start times - evening: {ASHA_EVENING} "
        "(12 in all); suggest first 17:00, 17:15, 17:30."
    )


def test_slots_offered_follows_clinic_setting(db):
    s, clinic_id = db
    repo.update_clinic(s, clinic_id, slots_offered=2)
    assert find(db, doctor_name="Asha").endswith("10:00, 10:15.")


def test_booked_slot_is_not_offered(db):
    book(db)
    assert "free start times - morning: 10:15, 10:30," in find(db, doctor_name="Asha")


def test_booked_slots_are_left_out(db):
    book(db, at=time(11, 0))
    book(db, at=time(11, 15), name="Sunita", phone="9123456780")
    out = find(db, doctor_name="Asha")
    assert "morning: 10:00, 10:15, 10:30, 10:45, 11:30, 11:45;" in out and "(22 in all)" in out


def test_a_lone_free_slot(db):
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    repo.set_doctor_hours(s, asha.id, [(1, time(10), time(10, 15))])
    assert find(db, doctor_name="Asha").endswith("free start times - morning: 10:00 (1 in all); suggest first 10:00.")


def test_clinic_holiday_gives_reason_and_next_day(db):
    s, clinic_id = db
    repo.add_time_off(s, clinic_id, TUE, TUE, reason="Ganesh Chaturthi")
    out = find(db, doctor_name="Asha")
    assert "none - clinic closed (Ganesh Chaturthi)" in out
    assert "Next free day: Wednesday 23 September 2026" in out


def test_doctor_leave(db):
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    repo.add_time_off(s, clinic_id, TUE, date(2026, 9, 23), doctor_id=asha.id)
    out = find(db, doctor_name="Asha")
    assert "none - doctor on leave" in out and "Next free day: Thursday 24 September 2026" in out


def test_after_the_days_last_slot_it_says_none_left_not_fully_booked(db):
    s, clinic_id = db
    evening = datetime(2026, 9, 21, 19, 45)  # Asha's last sitting ends at 20:00
    out = booking.find_slots(s, clinic_id, date(2026, 9, 21), evening, doctor_name="Asha")
    assert "none - no times left today." in out and "fully booked" not in out
    assert "Next free day: Tuesday 22 September 2026" in out


def test_a_part_of_day_the_doctor_never_sits_is_not_fully_booked(db):
    out = find(db, day=date(2026, 9, 23), doctor_name="Rohan", part_of_day="evening")
    assert "none - doctor does not sit in the evening on Wednesdays." in out


def test_fully_booked_still_says_so(db):
    s, clinic_id = db
    rohan = repo.get_clinic(s, clinic_id).doctors[1]
    wed = date(2026, 9, 23)
    for h in range(11, 14):
        for m in (0, 20, 40):
            repo.book(s, clinic_id, rohan.id, datetime.combine(wed, time(h, m)), f"P{h}{m}", "9876543210")
    assert "none - fully booked." in find(db, day=wed, doctor_name="Rohan")


def test_past_and_far_future_days_are_refused(db):
    with pytest.raises(BookingError, match="in the past"):
        find(db, day=date(2026, 9, 20))
    with pytest.raises(BookingError, match="30 days ahead"):
        find(db, day=date(2026, 11, 30))


def test_today_skips_times_already_gone(db):
    # 09:00 now, 30-minute lead: 10:00 is fine, and nothing before it exists anyway
    s, clinic_id = db
    late = datetime(2026, 9, 21, 10, 50)
    out = plain(booking.find_slots(s, clinic_id, date(2026, 9, 21), late, doctor_name="Asha"))
    assert "free start times - morning: 11:30, 11:45; afternoon: 12:00" in out


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
    with pytest.raises(BookingError, match=r"not free at 10:00.*That day: free start times - morning: 10:15 \(सवा दस बजे\)"):
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
    with pytest.raises(BookingError, match=r"just taken by another caller. That day: free start times - morning: 10:15 \(सवा दस बजे\)"):
        book(db)


def test_missing_name_and_bad_phone(db):
    with pytest.raises(BookingError, match="name is missing"):
        book(db, name="  ")
    with pytest.raises(BookingError, match="not a valid 10-digit"):
        book(db, phone="12345")


def test_two_calls_adding_the_same_new_patient_both_book(db, monkeypatch):
    # The other call inserts "Ravi" after our lookup found nobody: our insert
    # clashes on the patient, and the booking must retry with their row.
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    first = repo.book(s, clinic_id, asha.id, datetime(2026, 9, 22, 11, 0), "Ravi", "9876543210")
    real_patient, calls = repo._patient, []

    def stale_lookup(s_, clinic_id_, name, phone):
        calls.append(name)
        if len(calls) == 1:
            patient = repo.Patient(clinic_id=clinic_id_, name=name, phone=phone)
            s_.add(patient)
            return patient
        return real_patient(s_, clinic_id_, name, phone)

    monkeypatch.setattr(repo, "_patient", stale_lookup)
    out = book(db)
    assert out.startswith("Booked") and len(calls) == 2
    (appt,) = repo.appointments_on(s, clinic_id, TUE)[:1]
    assert appt.patient_id == first.patient_id


# ---------- the visit reason and staff bookings ----------

def test_a_call_booking_keeps_the_reason(db):
    s, clinic_id = db
    booking.book_slot(s, clinic_id, "Asha", TUE, time(10), "Ravi", "9876543210", NOW, reason="  बुखार   और खाँसी ")
    (appt,) = repo.appointments_on(s, clinic_id, TUE)
    assert appt.reason == "बुखार और खाँसी"
    # Health information: kept for staff, never read out on a call.
    assert booking.find_appointments(s, clinic_id, "9876543210", "Ravi", NOW).endswith("for Ravi.")


def test_staff_change_points_the_booking_at_the_right_patient(db):
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    a = booking.staff_book(s, clinic_id, asha.id, datetime(2026, 9, 22, 10), "Ravi", "9876543210")
    b = booking.staff_book(s, clinic_id, asha.id, datetime(2026, 9, 22, 11), "Ravi", "9876543210")
    booking.staff_change(s, clinic_id, a.id, doctor_id=asha.id, starts_at=a.starts_at,
                         patient_name="Ravi Kumar", patient_phone="9876543210", reason="")
    s.expire_all()
    assert repo.get_appointment(s, a.id).patient.name == "Ravi Kumar"
    assert repo.get_appointment(s, b.id).patient.name == "Ravi"  # never a rename


def test_staff_cant_move_a_cancelled_booking_but_can_fix_its_details(db):
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    a = booking.staff_book(s, clinic_id, asha.id, datetime(2026, 9, 22, 10), "Ravi", "9876543210")
    repo.cancel_appointment(s, a.id)
    with pytest.raises(BookingError, match="cancelled. Book a new one"):
        booking.staff_change(s, clinic_id, a.id, doctor_id=asha.id, starts_at=datetime(2026, 9, 22, 12),
                             patient_name="Ravi", patient_phone="9876543210", reason="")
    out = booking.staff_change(s, clinic_id, a.id, doctor_id=asha.id, starts_at=a.starts_at,
                               patient_name="Ravi", patient_phone="9876543210", reason="follow-up")
    assert out.reason == "follow-up"


def test_moving_within_its_own_slot_is_not_an_overlap_with_itself(db):
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    a = booking.staff_book(s, clinic_id, asha.id, datetime(2026, 9, 22, 10), "Ravi", "9876543210")
    out = booking.staff_change(s, clinic_id, a.id, doctor_id=asha.id, starts_at=datetime(2026, 9, 22, 10, 5),
                               patient_name="Ravi", patient_phone="9876543210", reason="")
    assert out.starts_at == datetime(2026, 9, 22, 10, 5)
