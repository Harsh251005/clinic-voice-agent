"""Problems, flagged: what opens an incident, what closes it, and who reads
what. The clinic reads plain words about its own clinic; the operator reads
everything, technically."""

from datetime import datetime, timedelta

import pytest

from fastapi.testclient import TestClient

from clinic_agent import incidents
from clinic_agent.config import load_settings
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for
from clinic_agent.store.models import utc_now
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
    repo.beat(s, "AW_test", "host", ["hi"], now)


def call(s, clinic_id, started, *, ended=True, outcome="booked", end_reason="caller_left", room="call-demo-x", errors=(),
         did=("stt", "llm", "tts"), test=False):
    """A call; `did` the parts that worked on it (a timing each: heard, replied, spoke)."""
    c = repo.start_call(s, clinic_id, room, "sarvam/saaras:v3 · sarvam/sarvam-105b · sarvam/bulbul:v3", "hi", started, test=test)
    if ended:
        events = [{"t_ms": 100, "kind": "error", "name": name, "duration_ms": None, "ok": False, "detail": "APIError, retried"}
                  for name in errors]
        events += [{"t_ms": 200, "kind": part, "name": "", "duration_ms": 300, "ok": True, "detail": ""} for part in did]
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


def test_a_line_left_out_of_the_check_in_is_flagged_until_it_is_back(db):
    s, _ = db
    repo.beat(s, "AW_test", "host", [], NOW)  # a worker that can't answer Hindi (an old one)
    sync(s)
    (inc,) = [i for i in repo.open_incidents(s) if i.kind == "language_off"]
    assert (inc.subject, inc.severity, inc.clinic_id) == ("hi", "critical", None)  # the only line: no calls
    repo.beat(s, "AW_test", "host", ["hi"], NOW + timedelta(seconds=30))
    sync(s, NOW + timedelta(seconds=30))
    assert "language_off" not in open_kinds(s)


def test_an_offline_worker_is_only_offline_not_every_line_off(db):
    s, _ = db
    sync(s)
    assert "worker_offline" in open_kinds(s) and "language_off" not in open_kinds(s)


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
    assert inc.subject == "sarvam/bulbul:v3" and inc.detail == "tts|3|APIError, retried"  # the voice part, 3 errors, the latest


def _closed(s, kind):
    (inc,) = [i for i in repo.list_incidents(s, since=NOW - timedelta(days=1)) if i.kind == kind and i.resolved_at]
    return inc.resolved_how


def test_a_failing_vendor_closes_once_a_later_call_shows_it_working(db):
    # Harsh, 2026-11-09: solved = gone, without waiting out the 15 minutes or clicking anything.
    s, clinic_id = db
    healthy(s)
    call(s, clinic_id, NOW - timedelta(minutes=6), errors=["sarvam/bulbul:v3"] * 3)
    sync(s)
    assert "vendor_errors" in open_kinds(s)
    call(s, clinic_id, NOW - timedelta(minutes=4), did=("stt", "llm"))  # hung up before she spoke: proves nothing
    sync(s)
    assert "vendor_errors" in open_kinds(s)
    call(s, clinic_id, NOW - timedelta(minutes=2), did=("stt", "llm", "tts"), test=True)  # a staff test call spoke fine
    sync(s)
    assert "vendor_errors" not in open_kinds(s) and _closed(s, "vendor_errors") == "fixed"
    call(s, clinic_id, NOW - timedelta(minutes=1), errors=["sarvam/bulbul:v3"])
    sync(s)
    assert "vendor_errors" not in open_kinds(s)  # one new error is not three: the old ones were before the fix


def test_another_vendor_working_does_not_close_the_failing_one(db):
    s, clinic_id = db
    healthy(s)
    call(s, clinic_id, NOW - timedelta(minutes=6), errors=["sarvam/bulbul:v3"] * 3)
    call(s, clinic_id, NOW - timedelta(minutes=2), errors=["sarvam/bulbul:v3"], did=("stt", "llm", "tts"))
    sync(s)
    assert "vendor_errors" in open_kinds(s)  # it spoke, but the voice also failed on that call


def test_failed_calls_close_when_the_clinics_next_call_ends_well(db):
    s, clinic_id = db
    healthy(s)
    call(s, clinic_id, NOW - timedelta(minutes=30), outcome="failed", end_reason="error")
    call(s, clinic_id, NOW - timedelta(minutes=25), outcome="failed", end_reason="error")
    sync(s)
    assert "calls_failing" in open_kinds(s, clinic_id)
    call(s, clinic_id, NOW - timedelta(minutes=5), test=True)  # Harsh's test call after the fix
    sync(s)
    assert "calls_failing" not in open_kinds(s, clinic_id) and _closed(s, "calls_failing") == "fixed"


def test_a_patient_who_could_not_connect_closes_when_a_call_connects_there(db):
    s, clinic_id = db
    healthy(s)
    incidents.report(s, "patients_cant_connect", NOW, clinic_id=clinic_id, subject="no_answer")
    sync(s, NOW + timedelta(minutes=1))
    assert "patients_cant_connect" in open_kinds(s)
    call(s, clinic_id, NOW + timedelta(minutes=2))
    sync(s, NOW + timedelta(minutes=3))
    assert "patients_cant_connect" not in open_kinds(s) and _closed(s, "patients_cant_connect") == "fixed"


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
    # A week or more ahead, at the start of one of her sittings: a fixed "in 7
    # days" landed on a day she doesn't work whenever today was that weekday,
    # and the booking itself then needed a call (it failed every Sunday).
    sitting = asha.hours[0]
    today = datetime.now().date()
    day = today + timedelta(days=7 + (sitting.weekday - today.weekday()) % 7)
    repo.book(s, clinic_id, asha.id, datetime.combine(day, sitting.start), "Ravi", "9876543210")
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
    assert _closed(s, "patients_cant_connect") == "quiet"  # nothing retried it: shown as gone quiet, not fixed
    incidents.report(s, "patients_cant_connect", NOW, clinic_id=clinic_id, subject="mic_blocked")
    assert len(repo.list_incidents(s, since=NOW - timedelta(days=1))) == 2  # a new one, the old kept as history


def test_clear_closes_an_event_when_the_thing_works_again(db):
    s, clinic_id = db
    incidents.report(s, "purge_failed", NOW)
    incidents.clear(s, "purge_failed", NOW)
    assert "purge_failed" not in open_kinds(s) and _closed(s, "purge_failed") == "fixed"
    for why in ("ConfigError", "NoSuggestion"):
        incidents.report(s, "hindi_names_failing", NOW, clinic_id=clinic_id, subject=why)
    incidents.clear(s, "hindi_names_failing", NOW, clinic_id=clinic_id, subject=None)  # every reason at once
    assert "hindi_names_failing" not in open_kinds(s)


# ---------- the API: who reads what ----------

def _sessions():
    return sessions_for(load_settings().database_url)


def test_clinic_reads_its_own_problems_in_plain_words(world):  # noqa: F811
    with _sessions()() as s:
        sync(s)  # no worker: offline, for everyone
        incidents.report(s, "vendor_errors", NOW, subject="sarvam/bulbul:v3", detail="tts|3|APIStatusError 402, fatal")
        incidents.report(s, "patients_cant_connect", NOW, clinic_id=world["cure"], subject="mic_blocked")
        incidents.report(s, "patients_cant_connect", NOW, clinic_id=world["demo"], subject="no_answer")
    c = client_as("reception@cure.in")
    got = c.get(f"/api/clinics/{world['cure']}/problems").json()
    titles = [p["title"] for p in got["open"]]
    assert titles[0] == "Your receptionist is offline. Patients calling now can't reach it."  # critical first
    assert "1 patient couldn't reach your receptionist: their browser blocked the microphone." in titles
    assert "Your receptionist is having trouble speaking to callers right now." in titles  # a vendor, in plain words
    assert not any("sarvam" in t.lower() or "402" in t or "didn't answer" in t for t in titles)  # no vendor names, codes or other clinic's


def test_a_line_off_reads_plainly_for_the_clinic_and_technically_for_the_operator(world):  # noqa: F811
    with _sessions()() as s:
        repo.beat(s, "AW_test", "host", [], NOW)
        sync(s)
    clinic = [p["title"] for p in client_as("reception@cure.in").get(f"/api/clinics/{world['cure']}/problems").json()["open"]]
    assert clinic == ["Patients can't call your receptionist right now."]
    admin = [p["title"] for p in client_as("harsh@example.com", admin=True).get("/api/admin/problems").json()["open"]]
    assert "The Hindi line is off: the worker started without a key it needs, so it takes no calls." in admin


def test_the_clinic_marks_its_own_problem_seen_but_not_a_system_one(world):  # noqa: F811
    with _sessions()() as s:
        now = utc_now()  # real time: saving "seen" re-checks problems, and an old report would have gone quiet
        sync(s, now)
        incidents.report(s, "patients_cant_connect", now, clinic_id=world["cure"], subject="dropped")
        mine = next(i.id for i in repo.open_incidents(s) if i.clinic_id == world["cure"])
        offline = next(i.id for i in repo.open_incidents(s) if i.kind == "worker_offline")
        incidents.report(s, "patients_cant_connect", now, clinic_id=world["demo"], subject="dropped")
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


def test_a_server_error_closes_when_that_page_answers_again(world, monkeypatch):  # noqa: F811
    from api.app import create_app
    from api.dashboard.access import Viewer, current_viewer

    app = create_app(load_settings())
    app.dependency_overrides[current_viewer] = lambda: Viewer(email="harsh@example.com", is_admin=True, clinic_ids=frozenset())
    real = repo.list_clinics
    monkeypatch.setattr(repo, "list_clinics", lambda s: (_ for _ in ()).throw(RuntimeError("boom")))
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.get("/api/admin/clinics").status_code == 500
        assert c.get("/healthz").status_code == 200  # another page working proves nothing
        with _sessions()() as s:
            assert "server_error" in open_kinds(s)
        monkeypatch.setattr(repo, "list_clinics", real)  # the fix
        assert c.get("/api/admin/clinics").status_code == 200
        with _sessions()() as s:
            assert "server_error" not in open_kinds(s)
            p = c.get("/api/admin/problems").json()
            (fixed,) = [x for x in p["recent"] if x["kind"] == "server_error"]
            assert fixed["resolved_how"] == "fixed"


def test_an_api_restart_still_closes_a_server_error_when_its_page_works(world):  # noqa: F811
    from api.app import create_app
    from api.dashboard.access import Viewer, current_viewer

    with _sessions()() as s:
        incidents.report(s, "server_error", NOW, subject="GET /api/admin/clinics · RuntimeError")
    app = create_app(load_settings())
    app.dependency_overrides[current_viewer] = lambda: Viewer(email="harsh@example.com", is_admin=True, clinic_ids=frozenset())
    with TestClient(app) as c:  # the lifespan reads the open ones at start
        assert c.get("/api/admin/clinics").status_code == 200
    with _sessions()() as s:
        assert "server_error" not in open_kinds(s)


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
        repo.beat(s, "AW_1", "host", ["hi"], utc_now())
    assert client.get("/healthz/worker").json()["online"] is True


def test_a_change_saved_in_the_dashboard_re_checks_problems_before_it_answers(world):  # noqa: F811
    # Harsh, 2026-11-09: fix it in the dashboard and the problem is gone at once, not half a minute later.
    c = client_as("harsh@example.com", admin=True)
    clinic = world["cure"]

    def open_here():
        return [p["kind"] for p in c.get("/api/admin/problems").json()["open"] if p["clinic_id"] == clinic]

    assert c.put(f"/api/admin/clinics/{clinic}/active", json={"active": False}).status_code == 200
    assert "clinic_paused" in open_here()  # no background check has run: the save itself checked
    assert c.put(f"/api/admin/clinics/{clinic}/active", json={"active": True}).status_code == 200
    assert "clinic_paused" not in open_here()


def test_a_failed_problem_check_never_fails_the_save(world, monkeypatch):  # noqa: F811
    c = client_as("harsh@example.com", admin=True)
    monkeypatch.setattr(incidents, "sync", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db hiccup")))
    assert c.put(f"/api/admin/clinics/{world['cure']}/active", json={"active": False}).status_code == 200


# ---------- precise words (Harsh, 2026-11-09: know at once what broke and what to do) ----------

from api.dashboard.problems import admin_words, clinic_words  # noqa: E402
from clinic_agent.store.models import Incident  # noqa: E402


def _vendor(detail, subject="sarvam/bulbul:v4-flash"):
    return Incident(kind="vendor_errors", subject=subject, detail=detail, count=1, severity="warning", clinic_id=None)


@pytest.mark.parametrize(("error", "says", "todo"), [
    ("APIStatusError 402, fatal", "out of credits (402)", "Top up your Sarvam account"),
    ("APIStatusError 401, fatal", "its key was rejected (401)", "Sarvam API key in backend/.env"),
    ("APIStatusError 429, retried", "too many requests (429)", "limiting you"),
    ("APIStatusError 503, retried", "Sarvam's own servers are failing (503)", "status page"),
    ("APITimeoutError, retried", "not answering in time", "internet connection"),
    ("APIConnectionError, retried", "can't be reached", "internet connection"),
    ("WeirdError, fatal", "errors (WeirdError, fatal)", "errors list"),
])
def test_a_vendor_error_says_what_it_means_and_what_to_do(error, says, todo):
    title, action, link = admin_words(_vendor(f"tts|3|{error}"), None)
    assert title == f"Sarvam bulbul:v4-flash voice (text to speech): {says}, 3 errors in 15 minutes."
    assert todo in action and "Clears by itself once a call shows it working" in action and link == "/admin/errors"


def test_an_old_vendor_detail_still_reads(db):
    title, _, _ = admin_words(_vendor("3 errors in 15 minutes; latest APIError"), None)
    assert title.startswith("Sarvam bulbul:v4-flash: errors (3 errors in 15 minutes; latest APIError)")


@pytest.mark.parametrize(("part", "trouble"), [("stt", "hearing callers"), ("llm", "answering callers"), ("tts", "speaking to callers")])
def test_the_clinic_hears_about_vendor_trouble_in_plain_words(part, trouble):
    title, action, link = clinic_words(_vendor(f"{part}|3|APIStatusError 402, fatal"), 1)
    assert title == f"Your receptionist is having trouble {trouble} right now."
    assert "402" not in title + action and "Sarvam" not in title + action and link is None  # no vendor names or codes
    assert "clears by itself" in action


def test_failed_calls_say_when_in_the_clinics_own_time(db):
    s, clinic_id = db
    healthy(s)
    call(s, clinic_id, datetime(2026, 9, 28, 7, 42), outcome="failed", end_reason="error")  # 1:12 PM in India
    call(s, clinic_id, datetime(2026, 9, 28, 7, 50), outcome="failed", end_reason="error")
    sync(s)
    (inc,) = [i for i in repo.open_incidents(s) if i.kind == "calls_failing"]
    assert inc.detail == "2|1:12 PM,1:20 PM"
    title, action, _ = clinic_words(inc, clinic_id)
    assert title == "2 calls to your receptionist failed at 1:12 PM and 1:20 PM."
    assert "ring them back" in action and "clears by itself" in action
    assert admin_words(inc, "Demo")[0] == "Demo: 2 calls failed or dropped (1:12 PM and 1:20 PM)."


def test_a_clinic_sees_a_failing_vendor_but_cannot_put_it_away(world):  # noqa: F811
    with _sessions()() as s:
        now = utc_now()
        incidents.report(s, "vendor_errors", now, subject="sarvam/bulbul:v3", detail="tts|3|APIStatusError 402, fatal")
        vendor = next(i.id for i in repo.open_incidents(s) if i.kind == "vendor_errors")
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}/problems"
    (p,) = [x for x in c.get(base).json()["open"] if x["kind"] == "vendor_errors"]
    assert p["title"] == "Your receptionist is having trouble speaking to callers right now." and p["can_mark_seen"] is False
    assert c.post(f"{base}/{vendor}/seen").status_code == 404
    admin = client_as("harsh@example.com", admin=True).get("/api/admin/problems").json()
    assert next(x for x in admin["open"] if x["kind"] == "vendor_errors")["can_mark_seen"] is True


def test_many_failed_calls_read_short():
    def title(times):
        inc = Incident(kind="calls_failing", detail=f"{len(times)}|{','.join(times)}", count=1, severity="warning", clinic_id=1)
        return clinic_words(inc, 1)[0]
    assert title(["5:18 PM", "5:18 PM", "5:18 PM"]) == "3 calls to your receptionist failed at 5:18 PM."
    assert title(["1:12 PM", "1:30 PM", "2:05 PM", "3:40 PM"]) == "4 calls to your receptionist failed between 1:12 PM and 3:40 PM."
