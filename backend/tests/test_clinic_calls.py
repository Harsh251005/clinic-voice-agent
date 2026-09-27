"""A clinic's own calls (/api/clinics/{id}/calls): its staff read what was
said and what changed, never the tools the receptionist used or vendor
errors, and they see every time ClinicDesk support opened a transcript."""

from datetime import timedelta

from clinic_agent.store import repo
from tests.test_admin_api import ADMIN, _call, _sessions, ev
from tests.test_dashboard_api import client_as, world  # noqa: F401 - the fixture

ITEMS = [
    {"t_ms": 0, "role": "agent", "text": "नमस्ते, Demo Family Clinic"},
    {"t_ms": 3000, "role": "caller", "text": "कल डॉक्टर आशा का टाइम है?", "interrupted": False},
    {"t_ms": 5000, "role": "tool", "tool": "check_booking", "ok": True, "args": '{"doctor": "Asha"}', "text": "Not booked yet."},
    {"t_ms": 5200, "role": "error", "text": "sarvam/bulbul:v3 APIConnectionError"},
    {"t_ms": 6000, "role": "agent", "text": "हाँ, सुबह दस बजे", "interrupted": True},
]


def _with_change(clinic_id, appt_id, action="booked"):
    call = _call(clinic_id, items=ITEMS, events=[ev("tool", 12, "check_booking")])
    with _sessions()() as s:
        repo.get_call(s, call).appointments = [{"id": appt_id, "action": action}]
        s.commit()
    return call


def test_staff_see_the_conversation_and_nothing_technical(world):  # noqa: F811
    call = _with_change(world["demo"], world["demo_appt"])
    staff = client_as("doctor@demo.in")
    r = staff.get(f"/api/clinics/{world['demo']}/calls/{call}")
    assert r.status_code == 200
    detail = r.json()
    assert [(line["role"], line["text"], line["interrupted"]) for line in detail["conversation"]] == [
        ("agent", "नमस्ते, Demo Family Clinic", False),
        ("caller", "कल डॉक्टर आशा का टाइम है?", False),
        ("agent", "हाँ, सुबह दस बजे", True),
    ]
    for technical in ("check_booking", "Not booked yet", "APIConnectionError", "sarvam", "openai", "stack"):
        assert technical not in r.text
    (change,) = detail["changes"]
    assert (change["action"], change["patient_name"], change["doctor_name"]) == ("booked", "Riya", "Dr. Asha Mehta")
    assert change["starts_at"] == "2026-12-07T10:00:00"
    assert (detail["status"], detail["duration_s"], detail["transcript_kept"]) == ("ended", 95, True)


def test_the_list_is_the_clinics_own_calls_newest_first(world):  # noqa: F811
    older = _call(world["demo"], ago=timedelta(hours=2))
    newer = _call(world["demo"], ago=timedelta(minutes=5))
    theirs = _call(world["cure"])
    rows = client_as("doctor@demo.in").get(f"/api/clinics/{world['demo']}/calls").json()
    ids = [r["id"] for r in rows]
    assert ids == [newer, older] and theirs not in ids
    assert "conversation" not in rows[0]  # words only on a call's own page
    before = client_as("doctor@demo.in").get(f"/api/clinics/{world['demo']}/calls", params={"before_id": newer}).json()
    assert newer not in [r["id"] for r in before]


def test_staff_see_when_support_opened_a_transcript_but_not_who(world):  # noqa: F811
    call = _call(world["demo"])
    admin = client_as(ADMIN, admin=True)
    admin.post(f"/api/admin/calls/{call}/transcript", json={"reason": "Caller said the booking was wrong"})
    (view,) = client_as("doctor@demo.in").get(f"/api/clinics/{world['demo']}/calls/{call}").json()["support_views"]
    assert view["reason"] == "Caller said the booking was wrong" and "email" not in view


def test_a_deleted_transcript_leaves_the_call_without_words(world):  # noqa: F811
    call = _call(world["demo"], ago=timedelta(days=40))
    from clinic_agent.store.purge import purge
    purge(_sessions())
    detail = client_as("doctor@demo.in").get(f"/api/clinics/{world['demo']}/calls/{call}").json()
    assert detail["transcript_kept"] is False and detail["conversation"] == []


def test_a_change_whose_appointment_was_deleted_still_shows(world):  # noqa: F811
    call = _with_change(world["demo"], 99999, "cancelled")
    (change,) = client_as("doctor@demo.in").get(f"/api/clinics/{world['demo']}/calls/{call}").json()["changes"]
    assert change == {"action": "cancelled", "appointment_id": 99999, "patient_name": None,
                      "doctor_name": None, "starts_at": None}


def test_a_change_pointing_at_another_clinics_appointment_shows_nothing_of_it(world):  # noqa: F811
    call = _with_change(world["demo"], world["cure_appt"])
    r = client_as("doctor@demo.in").get(f"/api/clinics/{world['demo']}/calls/{call}")
    assert r.json()["changes"][0]["patient_name"] is None and "Harsh" not in r.text


def test_today_counts_the_clinics_calls_and_flags_callers_not_helped(world, monkeypatch):  # noqa: F811
    # An hour behind the real clock: today's midnight is always before every call made below.
    from api.dashboard import calls
    real = calls.clinic_now
    monkeypatch.setattr(calls, "clinic_now", lambda tz: real(tz) - timedelta(hours=1))
    booked = _with_change(world["demo"], world["demo_appt"])
    _call(world["demo"], ago=timedelta(minutes=10), outcome="info_only")
    failed = _call(world["demo"], ago=timedelta(minutes=5), outcome="failed")
    dropped = _call(world["demo"], ago=timedelta(minutes=15), finished=False)  # past the time limit
    _call(world["demo"], ago=timedelta(minutes=1), finished=False)  # still on the line
    _call(world["demo"], ago=timedelta(days=2), outcome="failed")  # not today
    _call(world["cure"], ago=timedelta(minutes=5), outcome="failed")  # not this clinic
    today = client_as("doctor@demo.in").get(f"/api/clinics/{world['demo']}/calls/today").json()
    assert (today["calls"], today["changed"], today["questions"]) == (5, 1, 1)
    assert sorted(c["id"] for c in today["unhelped"]) == sorted([failed, dropped])
    assert booked not in [c["id"] for c in today["unhelped"]]


def test_the_clinic_knows_whether_its_receptionist_took_a_call(world):  # noqa: F811
    admin = client_as(ADMIN, admin=True)  # not patient data: the setup checklist is for admins too
    assert admin.get(f"/api/clinics/{world['demo']}").json()["has_calls"] is False
    _call(world["demo"])
    assert admin.get(f"/api/clinics/{world['demo']}").json()["has_calls"] is True
    assert admin.get(f"/api/clinics/{world['cure']}").json()["has_calls"] is False
