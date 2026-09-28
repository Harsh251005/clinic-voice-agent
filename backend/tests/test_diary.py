"""The appointments diary: visit marks (arrived, done, no-show), undoing a
cancellation, a doctor's day as the grid draws it, the week, and search."""

from datetime import date, datetime, time

import pytest

from clinic_agent import booking
from clinic_agent.booking import BookingError
from clinic_agent.store import repo
from tests.test_dashboard_api import client_as, world  # noqa: F401 - the fixture

NOW = datetime(2026, 9, 22, 9, 0)  # Tuesday morning
TUE, WED = date(2026, 9, 22), date(2026, 9, 23)
PHONE = "9876543210"


def _asha(s, clinic_id):
    return repo.get_clinic(s, clinic_id).doctors[0]


def _staff_booking(s, clinic_id, at=datetime(2026, 9, 22, 10), name="Ravi"):
    return booking.staff_book(s, clinic_id, _asha(s, clinic_id).id, at, name, PHONE)


# ---------- visit marks ----------

def test_visit_marks_on_the_day_and_cleared_again(db):
    s, clinic_id = db
    a = _staff_booking(s, clinic_id)
    for mark in ("arrived", "done", "no_show", None):
        assert booking.staff_visit(s, clinic_id, a.id, mark, NOW).visit == mark


def test_a_future_visit_cant_be_marked_but_a_past_one_can(db):
    s, clinic_id = db
    later = _staff_booking(s, clinic_id, at=datetime(2026, 9, 23, 10))
    with pytest.raises(BookingError, match="on the day of the appointment or later"):
        booking.staff_visit(s, clinic_id, later.id, "arrived", NOW)
    assert booking.staff_visit(s, clinic_id, later.id, None, NOW).visit is None  # clearing is always fine
    past = _staff_booking(s, clinic_id, at=datetime(2026, 9, 1, 10))
    assert booking.staff_visit(s, clinic_id, past.id, "no_show", NOW).visit == "no_show"


def test_a_cancelled_booking_cant_carry_a_visit(db):
    s, clinic_id = db
    a = _staff_booking(s, clinic_id)
    booking.staff_visit(s, clinic_id, a.id, "arrived", NOW)
    repo.cancel_appointment(s, a.id)
    assert repo.get_appointment(s, a.id).visit is None  # cancelling clears it
    with pytest.raises(BookingError, match="cancelled"):
        booking.staff_visit(s, clinic_id, a.id, "done", NOW)


def test_an_unknown_mark_is_refused(db):
    s, clinic_id = db
    a = _staff_booking(s, clinic_id)
    with pytest.raises(BookingError, match="isn't a visit mark"):
        booking.staff_visit(s, clinic_id, a.id, "left", NOW)


def test_moving_a_booking_clears_its_mark_but_editing_details_keeps_it(db):
    s, clinic_id = db
    a = _staff_booking(s, clinic_id)
    booking.staff_visit(s, clinic_id, a.id, "arrived", NOW)
    kept = booking.staff_change(s, clinic_id, a.id, doctor_id=a.doctor_id, starts_at=a.starts_at,
                                patient_name="Ravi", patient_phone=PHONE, reason="fever")
    assert kept.visit == "arrived"
    moved = booking.staff_change(s, clinic_id, a.id, doctor_id=a.doctor_id, starts_at=datetime(2026, 9, 22, 11),
                                 patient_name="Ravi", patient_phone=PHONE, reason="fever")
    assert moved.visit is None


def test_a_checked_in_patient_still_holds_the_slot(db):
    """The whole reason visit is not a status: the slot guard must still see it."""
    s, clinic_id = db
    a = _staff_booking(s, clinic_id)
    booking.staff_visit(s, clinic_id, a.id, "arrived", NOW)
    free = booking.free_times(s, clinic_id, a.doctor_id, TUE, NOW)
    assert datetime(2026, 9, 22, 10) not in free
    with pytest.raises(repo.SlotTaken):
        repo.book(s, clinic_id, a.doctor_id, datetime(2026, 9, 22, 10), "Meena", "9819022222")


def test_the_receptionist_cant_change_a_visit_already_under_way(db):
    s, clinic_id = db
    booking.book_slot(s, clinic_id, "Asha", TUE, time(10), "Ravi", PHONE, NOW)
    (appt,) = repo.upcoming_for_phone(s, clinic_id, PHONE, NOW)
    booking.staff_visit(s, clinic_id, appt.id, "arrived", NOW)
    with pytest.raises(BookingError, match="No upcoming appointments"):
        booking.find_appointments(s, clinic_id, PHONE, "Ravi", NOW)
    with pytest.raises(BookingError, match="under way at the clinic"):
        booking.cancel_booking(s, clinic_id, appt.id, PHONE, "Ravi", NOW)
    with pytest.raises(BookingError, match="under way at the clinic"):
        booking.reschedule_booking(s, clinic_id, appt.id, PHONE, "Ravi", WED, time(10), NOW)


# ---------- undo a cancellation ----------

def test_undo_brings_a_cancelled_booking_back(db):
    s, clinic_id = db
    a = _staff_booking(s, clinic_id)
    repo.cancel_appointment(s, a.id)
    assert booking.staff_restore(s, clinic_id, a.id).status == "booked"
    assert booking.staff_restore(s, clinic_id, a.id).status == "booked"  # twice is harmless


@pytest.mark.parametrize("taken_at", [datetime(2026, 9, 22, 10), datetime(2026, 9, 22, 10, 5)])
def test_undo_refuses_when_the_slot_was_taken_meanwhile(db, taken_at):
    s, clinic_id = db
    a = _staff_booking(s, clinic_id)
    repo.cancel_appointment(s, a.id)
    _staff_booking(s, clinic_id, at=taken_at, name="Meena")  # same slot, or overlapping it
    with pytest.raises(BookingError, match="10 am on 22 Sep was booked by someone else"):
        booking.staff_restore(s, clinic_id, a.id)
    assert repo.get_appointment(s, a.id).status == "cancelled"


# ---------- a doctor's day ----------

def test_day_plan_has_hours_and_free_slots(db):
    s, clinic_id = db
    asha = _asha(s, clinic_id)
    _staff_booking(s, clinic_id)  # 10:00
    plan = booking.day_plan(s, asha, TUE, [], NOW)
    assert plan.sittings == [(time(10), time(13)), (time(17), time(20))]
    assert plan.off is None
    assert plan.free[:2] == [datetime(2026, 9, 22, 10, 15), datetime(2026, 9, 22, 10, 30)]


def test_day_plan_says_why_the_doctor_is_out(db):
    s, clinic_id = db
    asha = _asha(s, clinic_id)
    repo.add_time_off(s, clinic_id, TUE, TUE, doctor_id=asha.id, reason="Wedding")
    plan = booking.day_plan(s, asha, TUE, repo.time_off_overlapping(s, clinic_id, TUE, TUE), NOW)
    assert (plan.off, plan.free) == ("On leave: Wedding", [])
    repo.add_time_off(s, clinic_id, TUE, TUE)  # the whole clinic, no reason
    plan = booking.day_plan(s, asha, TUE, repo.time_off_overlapping(s, clinic_id, TUE, TUE), NOW)
    assert plan.off == "Clinic closed"


# ---------- search ----------

def test_search_by_name_or_the_last_digits_of_the_number(db):
    s, clinic_id = db
    past = _staff_booking(s, clinic_id, at=datetime(2026, 9, 1, 10))
    soon = _staff_booking(s, clinic_id, at=datetime(2026, 9, 23, 10))
    later = _staff_booking(s, clinic_id, at=datetime(2026, 9, 30, 10))
    booking.staff_book(s, clinic_id, _asha(s, clinic_id).id, datetime(2026, 9, 24, 10), "Meena", "9819022222")
    by_name = repo.search_appointments(s, clinic_id, "rav", TUE)
    assert [a.id for a in by_name] == [soon.id, later.id, past.id]  # upcoming soonest first, then past
    assert [a.patient.name for a in repo.search_appointments(s, clinic_id, "22222", TUE)] == ["Meena"]
    assert repo.search_appointments(s, clinic_id, "%", TUE) == []  # a wildcard is just a character


# ---------- the API ----------

def test_day_brings_each_doctors_column(world):  # noqa: F811
    c = client_as("reception@cure.in")
    day = c.get(f"/api/clinics/{world['cure']}/appointments", params={"day": "2026-12-07"}).json()
    (doctor,) = day["doctors"]
    assert doctor["name"] == "Dr. Khushboo" and doctor["slot_minutes"] == 15
    assert doctor["sittings"] == [{"start": "10:00:00", "end": "13:00:00"}]
    assert doctor["free"][:2] == ["10:15:00", "10:30:00"]  # 10:00 is Harsh's
    closed = c.get(f"/api/clinics/{world['cure']}/appointments", params={"day": "2026-12-01"}).json()
    assert closed["doctors"][0]["off"] == "Clinic closed: Conference"


def test_week_brings_seven_days_and_each_doctors_state(world):  # noqa: F811
    c = client_as("reception@cure.in")
    week = c.get(f"/api/clinics/{world['cure']}/appointments/week", params={"start": "2026-12-01"}).json()
    assert [d["name"] for d in week["doctors"]] == ["Dr. Khushboo"]
    assert len(week["days"]) == 7
    tue, sun, mon = week["days"][0], week["days"][5], week["days"][6]
    assert tue["doctors"][0]["off"] == "Clinic closed: Conference"
    assert sun["doctors"][0]["sits"] is False
    assert [a["patient_name"] for a in mon["appointments"]] == ["Harsh"]
    assert mon["doctors"][0]["free"] == 11  # 10:00-13:00 in 15 minutes, less Harsh's


def test_visit_undo_and_search_over_the_api(world):  # noqa: F811
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    appt = world["cure_appt"]  # 7 December: not yet
    early = c.post(f"{base}/appointments/{appt}/visit", json={"visit": "arrived"})
    assert early.status_code == 422 and "on the day" in early.json()["detail"]
    bad = c.post(f"{base}/appointments/{appt}/visit", json={"visit": "left"})
    assert bad.status_code == 422

    c.post(f"{base}/appointments/{appt}/cancel")
    assert c.post(f"{base}/appointments/{appt}/restore").json()["status"] == "booked"

    found = c.get(f"{base}/appointments/search", params={"q": "3112"}).json()
    assert [a["patient_name"] for a in found] == ["Harsh"]
    assert c.get(f"{base}/appointments/search", params={"q": "H"}).json() == []  # too short to search
    assert c.get(f"{base}/appointments/search", params={"q": "Riya"}).json() == []  # the other clinic's


def test_a_past_visit_is_marked_over_the_api(world):  # noqa: F811
    from clinic_agent.config import load_settings
    from clinic_agent.store.db import sessions_for
    with sessions_for(load_settings().database_url)() as s:
        past = repo.book(s, world["cure"], world["khushboo"], datetime(2026, 1, 5, 10), "Asha", "9820011111").id
    c = client_as("reception@cure.in")
    r = c.post(f"/api/clinics/{world['cure']}/appointments/{past}/visit", json={"visit": "done"})
    assert r.json()["visit"] == "done"
    day = c.get(f"/api/clinics/{world['cure']}/appointments", params={"day": "2026-01-05"}).json()
    assert day["appointments"][0]["visit"] == "done"
