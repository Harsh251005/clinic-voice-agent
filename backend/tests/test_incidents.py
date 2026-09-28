"""Problems, flagged: what opens an incident, what closes it, and who reads
what. The clinic reads plain words about its own clinic; the operator reads
everything, technically."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from clinic_agent import incidents
from clinic_agent.config import load_settings
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for
from tests.test_api import client, seeded_url  # noqa: F401 - fixtures
from tests.test_dashboard_api import client_as, world  # noqa: F401 - fixtures

NOW = datetime(2026, 9, 28, 8, 0)  # UTC
LIMIT = 10  # MAX_CALL_MINUTES


def sync(s, now=NOW):
    incidents.sync(s, now, max_call_minutes=LIMIT)


def open_kinds(s, clinic_id=None):
    return sorted(i.kind for i in repo.open_incidents(s) if clinic_id is None or i.clinic_id == clinic_id)


def healthy(s, now=NOW):
    """A worker checking in, so only the problem under test is open."""
    repo.beat(s, "AW_test", "host", now)


def call(s, clinic_id, started, *, ended=True, outcome="booked", end_reason="caller_left", room="call-demo-x", errors=()):
    c = repo.start_call(s, clinic_id, room, "sarvam/saaras:v3 · sarvam/sarvam-105b · sarvam/bulbul:v3", started)
    if ended:
        events = [{"t_ms": 100, "kind": "error", "name": name, "duration_ms": None, "ok": False, "detail": "APIError, retried"}
                  for name in errors]
        repo.finish_call(s, c.id, ended_at=started + timedelta(minutes=2), end_reason=end_reason, outcome=outcome,
                         turn_count=1, error_count=len(errors), appointments=[], events=events, transcript=[],
                         purge_after=started + timedelta(days=30))
    return c


# ---------- the receptionist being up ----------

def test_no_worker_ever_is_offline_and_a_beat_brings_it_back(db):
    s, _ = db
    sync(s)
    (inc,) = [i for i in repo.open_incidents(s) if i.kind == "worker_offline"]
    assert (inc.severity, inc.clinic_id, inc.detail) == ("critical", None, "never")
    healthy(s, NOW)
    sync(s, NOW + timedelta(seconds=30))
    assert "worker_offline" not in open_kinds(s)


def test_three_missed_beats_mean_offline(db):
    s, _ = db
    healthy(s, NOW)
    sync(s, NOW + timedelta(seconds=90))
    assert "worker_offline" not in open_kinds(s)
    sync(s, NOW + timedelta(seconds=91))
    assert "worker_offline" in open_kinds(s)


# ---------- vendors and calls ----------

def test_a_vendor_failing_three_times_in_15_minutes(db):
    s, clinic_id = db
    healthy(s)
    call(s, clinic_id, NOW - timedelta(minutes=5), errors=["sarvam/bulbul:v3"] * 2)
    sync(s)
    assert "vendor_errors" not in open_kinds(s)
    call(s, clinic_id, NOW - timedelta(minutes=3), errors=["sarvam/bulbul:v3"])
    sync(s)
    (inc,) = [i for i in repo.open_incidents(s) if i.kind == "vendor_errors"]
    assert inc.subject == "sarvam/bulbul:v3" and inc.detail.startswith("3 errors in 15 minutes")


def test_calls_failing_counts_failed_and_dropped_but_not_the_console(db):
    s, clinic_id = db
    healthy(s)
    call(s, clinic_id, NOW - timedelta(minutes=30), outcome="failed", end_reason="error")
    call(s, clinic_id, NOW - timedelta(minutes=20), outcome="failed", end_reason="error", room=repo.CONSOLE_ROOM)
    sync(s)
    assert "calls_failing" not in open_kinds(s, clinic_id)  # one patient call; the console's is a test
    call(s, clinic_id, NOW - timedelta(minutes=LIMIT + 5), ended=False)  # the worker died mid-call
    sync(s)
    assert "calls_failing" in open_kinds(s, clinic_id)
    sync(s, NOW + timedelta(hours=2))  # an hour on with nothing failing
    assert "calls_failing" not in open_kinds(s, clinic_id)


def test_livekit_minutes_warn_then_turn_critical(db):
    s, clinic_id = db
    healthy(s)
    start = NOW.replace(day=1, hour=1)
    for i in range(400):  # 2 minutes each
        call(s, clinic_id, start + timedelta(minutes=3 * i))
    sync(s)
    (inc,) = [i for i in repo.open_incidents(s) if i.kind == "livekit_minutes"]
    assert (inc.severity, inc.detail) == ("warning", "800 of 1000 minutes this month")
    for i in range(80):
        call(s, clinic_id, start + timedelta(minutes=3 * (400 + i)))
    sync(s)
    (inc,) = [i for i in repo.open_incidents(s) if i.kind == "livekit_minutes"]
    assert inc.severity == "critical"


# ---------- the clinic's setup ----------

def test_setup_that_stops_bookings(db):
    s, clinic_id = db
    healthy(s)
    asha, rohan = repo.get_clinic(s, clinic_id).doctors
    repo.set_doctor_hours(s, rohan.id, [])
    sync(s)
    (inc,) = [i for i in repo.open_incidents(s) if i.kind == "doctor_no_hours"]
    assert (inc.subject, inc.detail) == (str(rohan.id), "Dr. Rohan Iyer")
    for d in (asha, rohan):
        repo.update_doctor(s, d.id, active=False)
    sync(s)
    assert open_kinds(s, clinic_id) == ["no_doctors"]  # an inactive doctor's hours don't matter
    repo.set_clinic_active(s, clinic_id, False)
    sync(s)
    assert open_kinds(s, clinic_id) == ["clinic_paused"]


def test_bookings_that_need_a_call(db):
    s, clinic_id = db
    healthy(s)
    asha = repo.get_clinic(s, clinic_id).doctors[0]
    day = datetime.now().date() + timedelta(days=7)
    repo.book(s, clinic_id, asha.id, datetime.combine(day, datetime.min.time()).replace(hour=10), "Ravi", "9876543210")
    sync(s)
    assert "bookings_need_call" not in open_kinds(s, clinic_id)
    repo.add_time_off(s, clinic_id, day, day, doctor_id=asha.id)
    sync(s)
    (inc,) = [i for i in repo.open_incidents(s) if i.kind == "bookings_need_call"]
    assert inc.detail == "1"


# ---------- events: counted, then closed after a quiet spell ----------

def test_reports_are_counted_on_one_incident_and_close_when_quiet(db):
    s, clinic_id = db
    healthy(s)
    for _ in range(3):
        incidents.report(s, "patients_cant_connect", NOW, clinic_id=clinic_id, subject="mic_blocked")
    (inc,) = repo.open_incidents(s)
    assert inc.count == 3
    healthy(s, NOW + timedelta(minutes=119))
    sync(s, NOW + timedelta(minutes=119))
    assert open_kinds(s) == ["patients_cant_connect"]
    healthy(s, NOW + timedelta(minutes=121))
    sync(s, NOW + timedelta(minutes=121))
    assert open_kinds(s) == []
    incidents.report(s, "patients_cant_connect", NOW, clinic_id=clinic_id, subject="mic_blocked")
    assert len(repo.list_incidents(s, since=NOW - timedelta(days=1))) == 2  # a new one, the old kept as history


def test_clear_closes_an_event_when_the_thing_works_again(db):
    s, _ = db
    incidents.report(s, "purge_failed", NOW)
    incidents.clear(s, "purge_failed", NOW)
    assert "purge_failed" not in open_kinds(s)


# ---------- the API: who reads what ----------

def _sessions():
    return sessions_for(load_settings().database_url)


def test_clinic_reads_its_own_problems_in_plain_words(world):  # noqa: F811
    with _sessions()() as s:
        sync(s)  # no worker: offline, for everyone
        incidents.report(s, "vendor_errors", NOW, subject="sarvam/bulbul:v3")  # the operator's business
        incidents.report(s, "patients_cant_connect", NOW, clinic_id=world["cure"], subject="mic_blocked")
        incidents.report(s, "patients_cant_connect", NOW, clinic_id=world["demo"], subject="no_answer")
    c = client_as("reception@cure.in")
    got = c.get(f"/api/clinics/{world['cure']}/problems").json()
    titles = [p["title"] for p in got["open"]]
    assert titles[0] == "Your receptionist is offline. Patients calling now can't reach it."  # critical first
    assert "1 patient couldn't reach your receptionist: their browser blocked the microphone." in titles
    assert not any("sarvam" in t or "answer" in t for t in titles)  # no vendors, no other clinic's


def test_the_clinic_marks_its_own_problem_seen_but_not_a_system_one(world):  # noqa: F811
    with _sessions()() as s:
        sync(s)
        incidents.report(s, "patients_cant_connect", NOW, clinic_id=world["cure"], subject="dropped")
        mine = next(i.id for i in repo.open_incidents(s) if i.clinic_id == world["cure"])
        offline = next(i.id for i in repo.open_incidents(s) if i.kind == "worker_offline")
        incidents.report(s, "patients_cant_connect", NOW, clinic_id=world["demo"], subject="dropped")
        theirs = next(i.id for i in repo.open_incidents(s) if i.clinic_id == world["demo"])
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}/problems"
    assert c.post(f"{base}/{mine}/seen").json()["seen"] is True
    assert c.post(f"{base}/{offline}/seen").status_code == 404
    assert c.post(f"{base}/{theirs}/seen").status_code == 404  # another clinic's, through your own URL
    admin_view = client_as("harsh@example.com", admin=True).get("/api/admin/problems").json()
    assert not next(p for p in admin_view["open"] if p["id"] == mine)["seen"]  # seen by the clinic only


def test_the_operator_reads_everything_technically(world):  # noqa: F811
    with _sessions()() as s:
        sync(s)
        incidents.report(s, "server_error", NOW, subject="GET /api/clinics/{clinic_id} · KeyError")
        incidents.report(s, "patients_cant_connect", NOW, clinic_id=world["demo"], subject="no_answer")
    admin = client_as("harsh@example.com", admin=True)
    titles = [p["title"] for p in admin.get("/api/admin/problems").json()["open"]]
    assert titles[0].startswith("Receptionist offline: no worker connected to LiveKit (never checked in)")
    assert "Server error: GET /api/clinics/{clinic_id} · KeyError, 1 time." in titles
    assert "Demo Family Clinic: 1 patient couldn't connect (no_answer)." in titles
    assert client_as("reception@cure.in").get("/api/admin/problems").status_code == 403


def test_an_unhandled_error_becomes_a_problem_without_the_request(world, monkeypatch):  # noqa: F811
    from api.app import create_app
    from api.dashboard.access import Viewer, current_viewer

    app = create_app(load_settings())
    app.dependency_overrides[current_viewer] = lambda: Viewer(email="harsh@example.com", is_admin=True, clinic_ids=frozenset())
    monkeypatch.setattr(repo, "list_clinics", lambda s: (_ for _ in ()).throw(RuntimeError("Riya 9820012345")))
    r = TestClient(app, raise_server_exceptions=False).get("/api/admin/clinics")
    assert r.status_code == 500 and "9820012345" not in r.text
    with _sessions()() as s:
        (inc,) = [i for i in repo.open_incidents(s) if i.kind == "server_error"]
    assert inc.subject == "GET /api/admin/clinics · RuntimeError"  # the route, never the message


# ---------- the patient's call page reporting trouble ----------

def test_the_call_page_reports_why_it_gave_up(client):  # noqa: F811
    r = client.post("/call/demo-family-clinic/report", json={"reason": "mic_blocked"})
    assert r.status_code == 204
    with _sessions()() as s:
        (inc,) = repo.open_incidents(s)
    assert (inc.kind, inc.subject) == ("patients_cant_connect", "mic_blocked")


def test_the_call_page_report_takes_only_fixed_codes(client):  # noqa: F811
    assert client.post("/call/demo-family-clinic/report", json={"reason": "my name is Riya"}).status_code == 422
    assert client.post("/call/no-such-clinic/report", json={"reason": "dropped"}).status_code == 404


def test_the_call_page_report_must_be_json(client):  # noqa: F811
    """A cross-site form can send text/plain without asking; JSON needs our origin."""
    r = client.post("/call/demo-family-clinic/report", content='{"reason": "dropped"}', headers={"content-type": "text/plain"})
    assert r.status_code == 415


def test_call_page_reports_are_rate_limited(client):  # noqa: F811
    codes = [client.post("/call/demo-family-clinic/report", json={"reason": "dropped"}).status_code for _ in range(11)]
    assert codes[:10] == [204] * 10 and codes[10] == 429


def test_worker_status_for_the_call_page(client):  # noqa: F811
    from clinic_agent.store.models import utc_now

    assert client.get("/healthz/worker").json() == {"online": False, "last_seen": None}
    with _sessions()() as s:
        repo.beat(s, "AW_1", "host", utc_now())
    assert client.get("/healthz/worker").json()["online"] is True
