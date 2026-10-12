"""Staff test calls: real calls, kept out of the counts, erasable with
everything they changed (Harsh, 2026-10-12)."""

from datetime import datetime, time, timedelta

import pytest

from clinic_agent import booking
from clinic_agent.dispatch import BadDispatch, CallFor, call_from, metadata_for
from clinic_agent.store import repo
from clinic_agent.store.models import Appointment, Call, Patient
from tests.test_dashboard_api import client_as, world, world_calls  # noqa: F401 - fixtures

DAY = datetime(2026, 12, 7)


def _call(s, clinic_id, changes, *, test=True, room="test-demo-1", ended=True):
    call = repo.start_call(s, clinic_id, room, "stack", "hi", DAY.replace(hour=9), test)
    if ended:
        repo.finish_call(s, call.id, ended_at=DAY.replace(hour=9, minute=3), end_reason="agent_ended",
                         outcome="booked", turn_count=2, error_count=0, appointments=changes,
                         events=[{"t_ms": 10, "kind": "tool", "name": "book_appointment", "duration_ms": 5, "ok": True, "detail": ""}],
                         transcript=[{"t_ms": 0, "role": "caller", "text": "Namaste"}],
                         purge_after=DAY + timedelta(days=30))
    return call.id


def _doctor(s, clinic_id):
    return repo.get_clinic(s, clinic_id).doctors[0]


# ---------- dispatch ----------

def test_a_test_call_says_so_in_its_dispatch():
    assert call_from(metadata_for(3, "en", test=True)) == CallFor(3, "en", test=True)
    assert call_from(metadata_for(3, "en")) == CallFor(3, "en", test=False)
    with pytest.raises(BadDispatch):
        call_from('{"clinic_id": 3, "language": "en", "test": "yes"}')


# ---------- erasing ----------

def test_erasing_deletes_its_booking_its_new_patient_and_the_call(db):
    s, clinic_id = db
    doc = _doctor(s, clinic_id)
    appt = repo.book(s, clinic_id, doc.id, DAY.replace(hour=10), "Test Patient", "9000000001")
    patient_id = appt.patient_id
    call_id = _call(s, clinic_id, [{"id": appt.id, "action": "booked"}])

    booking.erase_test_call(s, clinic_id, call_id)
    assert s.get(Appointment, appt.id) is None and s.get(Patient, patient_id) is None
    assert s.get(Call, call_id) is None
    assert repo.call_events(s, [call_id]) == [] and not repo.has_transcript(s, call_id)


def test_a_patient_with_other_appointments_is_kept(db):
    s, clinic_id = db
    doc = _doctor(s, clinic_id)
    earlier = repo.book(s, clinic_id, doc.id, DAY.replace(hour=10), "Riya", "9000000002")
    by_test = repo.book(s, clinic_id, doc.id, DAY.replace(hour=11), "Riya", "9000000002")
    booking.erase_test_call(s, clinic_id, _call(s, clinic_id, [{"id": by_test.id, "action": "booked"}]))
    assert s.get(Appointment, earlier.id) is not None and s.get(Patient, earlier.patient_id) is not None


def test_erasing_puts_back_a_cancellation_and_a_move(db):
    s, clinic_id = db
    doc = _doctor(s, clinic_id)
    cancelled = repo.book(s, clinic_id, doc.id, DAY.replace(hour=10), "Riya", "9000000003")
    moved = repo.book(s, clinic_id, doc.id, DAY.replace(hour=11), "Aman", "9000000004")
    was = {"doctor_id": doc.id, "starts_at": moved.starts_at.isoformat(), "ends_at": moved.ends_at.isoformat()}
    repo.cancel_appointment(s, cancelled.id)
    repo.move_appointment(s, moved.id, doc.id, DAY.replace(hour=12))
    call_id = _call(s, clinic_id, [{"id": cancelled.id, "action": "cancelled"},
                                   {"id": moved.id, "action": "moved", "undo": was}])

    booking.erase_test_call(s, clinic_id, call_id)
    s.expire_all()
    assert s.get(Appointment, cancelled.id).status == "booked"
    assert s.get(Appointment, moved.id).starts_at == DAY.replace(hour=11)


def test_a_booking_made_and_cancelled_on_the_same_call_is_gone(db):
    s, clinic_id = db
    appt = repo.book(s, clinic_id, _doctor(s, clinic_id).id, DAY.replace(hour=10), "Test", "9000000005")
    repo.cancel_appointment(s, appt.id)
    booking.erase_test_call(s, clinic_id, _call(s, clinic_id, [{"id": appt.id, "action": "booked"},
                                                                {"id": appt.id, "action": "cancelled"}]))
    assert s.get(Appointment, appt.id) is None


def test_a_slot_taken_since_stops_the_erase_and_changes_nothing(db):
    # All or nothing: half an erase would leave the diary in a state nobody chose.
    s, clinic_id = db
    doc = _doctor(s, clinic_id)
    booked = repo.book(s, clinic_id, doc.id, DAY.replace(hour=9), "Test", "9000000006")
    cancelled = repo.book(s, clinic_id, doc.id, DAY.replace(hour=10), "Riya", "9000000007")
    repo.cancel_appointment(s, cancelled.id)
    call_id = _call(s, clinic_id, [{"id": booked.id, "action": "booked"}, {"id": cancelled.id, "action": "cancelled"}])
    repo.book(s, clinic_id, doc.id, DAY.replace(hour=10), "Someone Else", "9000000008")  # took the freed slot

    with pytest.raises(booking.BookingError, match=r"can't be erased yet: .*'s 10 am on 7 Dec was booked by someone else.*Nothing was changed"):
        booking.erase_test_call(s, clinic_id, call_id)
    s.expire_all()
    assert s.get(Appointment, booked.id) is not None and s.get(Call, call_id) is not None


def test_a_patients_call_is_never_erased(db):
    s, clinic_id = db
    call_id = _call(s, clinic_id, [], test=False, room="call-demo-1")
    with pytest.raises(ValueError, match="Only test calls"):
        booking.erase_test_call(s, clinic_id, call_id)


def test_a_move_records_where_it_was_so_it_can_be_undone(db):
    s, clinic_id = db
    doc = _doctor(s, clinic_id)
    now = datetime.combine(DAY.date() - timedelta(days=1), time(9))
    day = DAY.date()
    while not any(h.weekday == day.weekday() for h in doc.hours):
        day += timedelta(days=1)
    first = sorted(h.start for h in doc.hours if h.weekday == day.weekday())[0]
    appt = repo.book(s, clinic_id, doc.id, datetime.combine(day, first), "Riya", "9000000009")
    later = (datetime.combine(day, first) + timedelta(minutes=doc.slot_minutes)).time()
    changed = booking.reschedule_booking(s, clinic_id, appt.id, "9000000009", "Riya", day, later, now)
    assert changed.undo == {"doctor_id": doc.id, "starts_at": datetime.combine(day, first).isoformat(),
                            "ends_at": (datetime.combine(day, first) + timedelta(minutes=doc.slot_minutes)).isoformat()}


def test_erasing_several_undoes_the_later_call_first(db):
    # Call 1 booked it, call 2 moved it: putting the move back, then deleting
    # the booking, leaves nothing behind.
    s, clinic_id = db
    doc = _doctor(s, clinic_id)
    appt = repo.book(s, clinic_id, doc.id, DAY.replace(hour=10), "Test", "9000000010")
    first = _call(s, clinic_id, [{"id": appt.id, "action": "booked"}])
    was = {"doctor_id": doc.id, "starts_at": appt.starts_at.isoformat(), "ends_at": appt.ends_at.isoformat()}
    repo.move_appointment(s, appt.id, doc.id, DAY.replace(hour=11))
    second = _call(s, clinic_id, [{"id": appt.id, "action": "moved", "undo": was}], room="test-demo-2")
    booking.erase_test_calls(s, clinic_id, [first, second])
    assert s.get(Appointment, appt.id) is None
    assert s.get(Call, first) is None and s.get(Call, second) is None


def test_erasing_several_is_all_or_nothing(db):
    s, clinic_id = db
    doc = _doctor(s, clinic_id)
    booked = repo.book(s, clinic_id, doc.id, DAY.replace(hour=9), "Test", "9000000011")
    first = _call(s, clinic_id, [{"id": booked.id, "action": "booked"}])
    cancelled = repo.book(s, clinic_id, doc.id, DAY.replace(hour=10), "Riya", "9000000012")
    repo.cancel_appointment(s, cancelled.id)
    second = _call(s, clinic_id, [{"id": cancelled.id, "action": "cancelled"}], room="test-demo-2")
    repo.book(s, clinic_id, doc.id, DAY.replace(hour=10), "Someone Else", "9000000013")
    with pytest.raises(booking.BookingError, match="These test calls can't be erased yet"):
        booking.erase_test_calls(s, clinic_id, [first, second])
    s.expire_all()
    assert s.get(Appointment, booked.id) is not None  # the first call's undo didn't happen either
    assert s.get(Call, first) is not None and s.get(Call, second) is not None


# ---------- counts ----------

def test_test_calls_stay_out_of_patient_counts_but_not_livekit_minutes(db):
    s, clinic_id = db
    _call(s, clinic_id, [])
    _call(s, clinic_id, [], test=False, room="call-demo-2")
    assert [c.test for c in repo.patient_calls_since(s, DAY)] == [False]
    assert len(repo.patient_calls_since(s, DAY, with_tests=True)) == 2


# ---------- the dashboard ----------

def _beat():
    from clinic_agent.config import load_settings
    from clinic_agent.store.db import sessions_for
    from clinic_agent.store.models import utc_now

    with sessions_for(load_settings().database_url)() as s:
        repo.beat(s, "AW_1", "host", ["en", "hi"], utc_now())


def test_staff_get_a_test_pass_that_dispatches_a_test_call(world):  # noqa: F811
    from livekit import api as lk

    from tests.test_dashboard_api import SECRET

    r = client_as("reception@cure.in").post(f"/api/clinics/{world['cure']}/calls/test", json={"language": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body["room"].startswith("test-cure-dental-clinic-")
    (dispatch,) = lk.TokenVerifier("APIkey", SECRET).verify(body["token"]).room_config.agents
    assert call_from(dispatch.metadata) == CallFor(world["cure"], "en", test=True)


def test_a_test_pass_is_refused_for_a_line_that_is_off(world):  # noqa: F811
    from clinic_agent.config import load_settings
    from clinic_agent.store.db import sessions_for
    from clinic_agent.store.models import utc_now

    with sessions_for(load_settings().database_url)() as s:
        repo.beat(s, "AW_1", "host", ["en"], utc_now())
    r = client_as("reception@cure.in").post(f"/api/clinics/{world['cure']}/calls/test", json={"language": "hi"})
    assert r.status_code == 409 and r.json()["detail"] == "Calls in Hindi aren't available right now."


def test_staff_find_their_test_call_by_room_and_erase_it(world):  # noqa: F811
    from clinic_agent.config import load_settings
    from clinic_agent.store.db import sessions_for

    with sessions_for(load_settings().database_url)() as s:
        call_id = _call(s, world["cure"], [{"id": world["cure_appt"], "action": "booked"}], room="test-cure-1")
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}/calls"
    found = c.get(f"{base}/by-room/test-cure-1").json()
    assert (found["id"], found["test"]) == (call_id, True)
    assert c.get(f"{base}/today").json()["calls"] == 0  # not a patient calling
    assert c.delete(f"{base}/{call_id}").status_code == 204
    assert c.get(f"{base}/{call_id}").status_code == 404
    with sessions_for(load_settings().database_url)() as s:
        assert s.get(Appointment, world["cure_appt"]) is None  # what it booked is gone too


def test_a_patients_call_and_a_live_test_call_cant_be_erased(world_calls):  # noqa: F811
    from clinic_agent.config import load_settings
    from clinic_agent.store.db import sessions_for
    from clinic_agent.store.models import utc_now

    world = world_calls
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}/calls"
    r = c.delete(f"{base}/{world['cure_call']}")
    assert r.status_code == 422 and "Patients' calls are kept" in r.json()["detail"]
    with sessions_for(load_settings().database_url)() as s:
        live = repo.start_call(s, world["cure"], "test-cure-2", "stack", "hi", utc_now(), True).id
    r = c.delete(f"{base}/{live}")
    assert r.status_code == 409 and "still going" in r.json()["detail"]


def test_talk_to_receptionist_counts_and_erases_every_finished_test_call(world_calls):  # noqa: F811
    from clinic_agent.config import load_settings
    from clinic_agent.store.db import sessions_for
    from clinic_agent.store.models import utc_now

    world = world_calls
    with sessions_for(load_settings().database_url)() as s:
        done = [_call(s, world["cure"], [], room=f"test-cure-{i}") for i in range(2)]
        live = repo.start_call(s, world["cure"], "test-cure-live", "stack", "hi", utc_now(), True).id
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}/calls/tests"
    assert c.get(base).json() == {"count": 3, "erasable": 2}
    assert c.delete(base).json() == {"erased": 2}
    assert c.get(base).json() == {"count": 1, "erasable": 0}  # the one still going stays
    with sessions_for(load_settings().database_url)() as s:
        assert [s.get(Call, i) for i in done] == [None, None] and s.get(Call, live) is not None
        assert s.get(Call, world["cure_call"]) is not None  # a patient's call is never touched
