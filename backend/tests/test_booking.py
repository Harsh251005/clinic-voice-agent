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


@pytest.mark.parametrize("spoken", ["डॉक्टर आशा", "डॉ. आशा मेहता", "आशा", "डॉक्टर आशा मेहता"])
def test_the_hindi_spelling_of_a_doctor_resolves(db, spoken):
    # Seen 2026-11-10: the prompt says 'say "डॉक्टर हर्ष"', the model passed
    # that to every tool and each one answered "No doctor called".
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    repo.update_doctor(s, asha.id, name_hi="डॉक्टर आशा मेहता")
    s.expire_all()
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

def test_offers_only_the_first_few_free_times_per_doctor(db):
    # Harsh, 2026-11-10: with the whole day listed the agent offered 5-6 times;
    # now it only ever sees the clinic's "free times offered at once" (3).
    out = find(db)
    assert (
        "Dr. Asha Mehta on Tuesday 22 September 2026: offer these free times: 10:00, 10:15, 10:30. "
        "Never offer any other time. More later that day: for those, call again with from_time after 10:30."
    ) in out
    assert "10:45" not in out and "17:00" not in out
    # Rohan doesn't sit on Tuesdays: says why and the next free day's first few
    assert "Dr. Rohan Iyer on Tuesday 22 September 2026: none - doctor does not sit on Tuesdays." in out
    assert "Next free day: Wednesday 23 September 2026, offer these free times: 11:00, 11:20, 11:40." in out


def test_from_a_time_gives_the_next_few_after_it(db):
    # "Evening?" -> the agent asks from 17:00; "after 12:30" -> from 12:30.
    assert find(db, doctor_name="Asha", from_time=time(17)).startswith(
        "Dr. Asha Mehta on Tuesday 22 September 2026: offer these free times: 17:00, 17:15, 17:30.")
    assert "offer these free times: 12:30, 12:45, 17:00." in find(db, doctor_name="Asha", from_time=time(12, 30))
    # A time between slots starts at the next free one.
    assert "offer these free times: 10:15, 10:30, 10:45." in find(db, doctor_name="Asha", from_time=time(10, 5))


def test_the_days_last_times_say_there_are_no_more(db):
    out = find(db, doctor_name="Asha", from_time=time(19, 15))
    assert "offer these free times: 19:15, 19:30, 19:45. Never offer any other time. No more free times that day." in out


def test_nothing_after_the_time_asked_names_the_next_free_day(db):
    out = find(db, doctor_name="Asha", from_time=time(20))
    assert "none - no free times from 20:00." in out
    assert "Next free day: Wednesday 23 September 2026" in out


def test_each_time_carries_the_hindi_words_for_it(db):
    # Left alone the LLM said "बारह साढ़े बजे" and "सत्रह बजे".
    s, clinic_id = db
    out = booking.find_slots(s, clinic_id, TUE, NOW, doctor_name="Asha", from_time=time(12, 30))
    assert "12:30 (साढ़े बारह बजे), 12:45 (पौने एक बजे), 17:00 (पाँच बजे)" in out


def test_slots_offered_follows_clinic_setting(db):
    s, clinic_id = db
    repo.update_clinic(s, clinic_id, slots_offered=2)
    assert "offer these free times: 10:00, 10:15. " in find(db, doctor_name="Asha")


def test_booked_slots_are_left_out(db):
    book(db, at=time(10, 15))
    book(db, at=time(10, 30), name="Sunita", phone="9123456780")
    assert "offer these free times: 10:00, 10:45, 11:00." in find(db, doctor_name="Asha")


def test_a_lone_free_slot(db):
    s, clinic_id = db
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    repo.set_doctor_hours(s, asha.id, [(1, time(10), time(10, 15))])
    assert find(db, doctor_name="Asha").endswith(
        "offer these free times: 10:00. Never offer any other time. No more free times that day.")


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
    assert "offer these free times: 11:30, 11:45, 12:00." in out


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
    with pytest.raises(BookingError, match=r"not free at 10:00.*That day, offer these free times: 10:15 \(सवा दस बजे\)"):
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
    with pytest.raises(BookingError, match=r"just taken by another caller. That day, offer these free times: 10:15 \(सवा दस बजे\)"):
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
