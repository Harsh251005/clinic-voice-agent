"""The operator's panel (/api/admin): admins only; traces and health without
a word from any call; a transcript only after a logged reason; pausing and
deleting clinics."""

from datetime import timedelta

import pytest

from clinic_agent.config import load_settings
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for
from clinic_agent.store.models import Call, Clinic, utc_now
from tests.test_dashboard_api import client_as, world  # noqa: F401 - the fixture

ADMIN = "harsh@example.com"
SAID = "मेरा नंबर 9876543210 है, बुखार है"


def _sessions():
    return sessions_for(load_settings().database_url)


def _call(clinic_id, *, ago=timedelta(hours=1), outcome="booked", finished=True, events=(), items=None):
    started = utc_now() - ago
    with _sessions()() as s:
        call = repo.start_call(s, clinic_id, "room", "sarvam/saaras:v3 · openai/gpt-6-luna · sarvam/bulbul:v3", started)
        if finished:
            repo.finish_call(
                s, call.id, ended_at=started + timedelta(seconds=95), end_reason="agent_ended", outcome=outcome,
                turn_count=3, error_count=sum(1 for e in events if e["kind"] == "error"), appointments=[],
                events=list(events), purge_after=started + timedelta(days=30),
                transcript=items if items is not None else [{"t_ms": 0, "role": "caller", "text": SAID}],
            )
        return call.id


def ev(kind, ms=None, name="", ok=True, detail="", t=0):
    return {"t_ms": t, "kind": kind, "name": name, "duration_ms": ms, "ok": ok, "detail": detail}


ROUTES = [
    ("GET", "/api/admin/health"), ("GET", "/api/admin/calls"), ("GET", "/api/admin/calls/{call}"),
    ("POST", "/api/admin/calls/{call}/transcript"), ("GET", "/api/admin/errors"), ("GET", "/api/admin/clinics"),
    ("PUT", "/api/admin/clinics/{cure}/active"), ("DELETE", "/api/admin/clinics/{cure}"),
]


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_only_admins(world, method, path):  # noqa: F811
    call = _call(world["cure"])
    r = client_as("reception@cure.in").request(
        method, path.format(call=call, **world), json={"reason": "checking", "active": False, "confirm_name": "x"})
    assert r.status_code == 403


def test_calls_and_traces_hold_no_words(world):  # noqa: F811
    call = _call(world["cure"], events=[ev("tool", 12, "check_booking"), ev("tool", 9, "book_appointment", ok=False),
                                        ev("llm", 640), ev("error", None, "sarvam/saaras:v3", False, "APIStatusError 503, retried")])
    c = client_as(ADMIN, admin=True)
    (row,) = c.get("/api/admin/calls").json()
    assert (row["id"], row["clinic_name"], row["status"], row["duration_s"]) == (call, "Cure Dental Clinic", "ended", 95)
    assert (row["tool_failures"], row["error_count"]) == (1, 1)
    assert row["started_at"].endswith("Z") or row["started_at"].endswith("+00:00")
    trace = c.get(f"/api/admin/calls/{call}")
    assert [e["kind"] for e in trace.json()["events"]] == ["tool", "tool", "llm", "error"]
    assert trace.json()["transcript_kept"] is True and trace.json()["accesses"] == []
    for body in (trace.text, c.get("/api/admin/calls").text, c.get("/api/admin/health").text, c.get("/api/admin/errors").text):
        assert "9876543210" not in body and "बुखार" not in body


def test_a_transcript_opens_only_with_a_logged_reason(world):  # noqa: F811
    call = _call(world["cure"])
    c = client_as(ADMIN, admin=True)
    assert c.post(f"/api/admin/calls/{call}/transcript", json={"reason": ""}).status_code == 422
    assert c.get(f"/api/admin/calls/{call}").json()["accesses"] == []
    r = c.post(f"/api/admin/calls/{call}/transcript", json={"reason": "  Agent booked the wrong day  "})
    assert r.json() == [{"t_ms": 0, "role": "caller", "text": SAID, "tool": None, "ok": None, "args": None, "interrupted": False}]
    (access,) = c.get(f"/api/admin/calls/{call}").json()["accesses"]
    assert (access["email"], access["reason"]) == (ADMIN, "Agent booked the wrong day")


def test_a_deleted_transcript_says_so_and_logs_nothing(world):  # noqa: F811
    call = _call(world["cure"], ago=timedelta(days=40))
    from clinic_agent.store.purge import purge
    purge(_sessions())
    c = client_as(ADMIN, admin=True)
    r = c.post(f"/api/admin/calls/{call}/transcript", json={"reason": "why did it fail"})
    assert r.status_code == 404 and "deleted after 30 days" in r.json()["detail"]
    trace = c.get(f"/api/admin/calls/{call}").json()
    assert trace["transcript_kept"] is False and trace["accesses"] == []
    assert c.post("/api/admin/calls/99999/transcript", json={"reason": "no such call"}).status_code == 404


def test_a_call_the_worker_never_finished_is_dropped(world):  # noqa: F811
    old = _call(world["cure"], ago=timedelta(hours=2), finished=False)
    live = _call(world["cure"], ago=timedelta(minutes=1), finished=False)
    c = client_as(ADMIN, admin=True)
    status = {r["id"]: r["status"] for r in c.get("/api/admin/calls").json()}
    assert status == {old: "dropped", live: "live"}
    assert [r["id"] for r in c.get("/api/admin/calls", params={"status": "dropped"}).json()] == [old]
    health = c.get("/api/admin/health").json()
    assert health["dropped"] == 1 and health["attention"][0]["kind"] == "dropped"


def test_health_numbers(world):  # noqa: F811
    for ms in (400, 500, 600, 700, 2000):
        _call(world["cure"], events=[ev("llm", ms), ev("reply", ms + 300)])
    _call(world["demo"], outcome="info_only", events=[ev("error", None, "openai/gpt-6-luna", False, "APITimeoutError, fatal")])
    _call(world["demo"], ago=timedelta(days=10))  # outside the week
    h = client_as(ADMIN, admin=True).get("/api/admin/health").json()
    assert (h["calls"], h["outcomes"], h["with_errors"]) == (6, {"booked": 5, "info_only": 1}, 1)
    llm = next(s for s in h["stages"] if s["stage"] == "llm")
    assert (llm["count"], llm["p50_ms"], llm["p95_ms"]) == (5, 600, 2000)
    assert [s["stage"] for s in h["stages"]] == ["llm", "reply"]
    assert h["vendors"] == [{"name": "openai/gpt-6-luna", "errors": 1, "calls": 1}]


def test_errors_are_grouped_newest_first(world):  # noqa: F811
    boom = ev("error", None, "sarvam/bulbul:v3", False, "APIConnectionError, retried")
    first = _call(world["cure"], ago=timedelta(hours=5), events=[boom, boom])
    second = _call(world["demo"], ago=timedelta(hours=1), events=[boom])
    other = _call(world["demo"], ago=timedelta(hours=3), events=[ev("error", None, "openai/gpt-6-luna", False, "APIStatusError 429, retried")])
    groups = client_as(ADMIN, admin=True).get("/api/admin/errors").json()
    assert [(g["name"], g["count"], g["call_ids"]) for g in groups] == [
        ("sarvam/bulbul:v3", 3, [second, first]), ("openai/gpt-6-luna", 1, [other])]


def test_clinics_list_with_their_calls(world):  # noqa: F811
    _call(world["cure"], events=[ev("error", None, "x", False)])
    _call(world["cure"])
    rows = {c["name"]: c for c in client_as(ADMIN, admin=True).get("/api/admin/clinics").json()}
    cure = rows["Cure Dental Clinic"]
    assert (cure["active"], cure["doctors"], cure["calls_7d"], cure["calls_with_errors_7d"]) == (True, 1, 2, 1)
    assert [m["email"] for m in cure["members"]] == ["reception@cure.in"]
    assert rows["Demo Family Clinic"]["last_call_at"] is None


def test_a_paused_clinic_takes_no_calls(world):  # noqa: F811
    c = client_as(ADMIN, admin=True)
    assert c.put(f"/api/admin/clinics/{world['cure']}/active", json={"active": False}).json()["active"] is False
    page = c.get("/call/cure-dental-clinic")
    assert page.status_code == 503 and "isn't taking calls" in page.text
    assert c.post("/call/cure-dental-clinic/pass").status_code == 503
    c.put(f"/api/admin/clinics/{world['cure']}/active", json={"active": True})
    assert c.get("/call/cure-dental-clinic").status_code == 200


def test_deleting_a_clinic_needs_a_pause_and_its_name_then_removes_everything(world):  # noqa: F811
    _call(world["cure"])
    c = client_as(ADMIN, admin=True)
    url = f"/api/admin/clinics/{world['cure']}"
    r = c.request("DELETE", url, json={"confirm_name": "Cure Dental Clinic"})
    assert r.status_code == 422 and "Pause" in r.json()["detail"]
    c.put(f"{url}/active", json={"active": False})
    r = c.request("DELETE", url, json={"confirm_name": "cure dental"})
    assert r.status_code == 422 and "exactly" in r.json()["detail"]
    assert c.request("DELETE", url, json={"confirm_name": "Cure Dental Clinic"}).json() == {"ok": True}

    with _sessions()() as s:
        assert s.get(Clinic, world["cure"]) is None
        assert s.query(Call).filter_by(clinic_id=world["cure"]).count() == 0
        assert repo.list_members(s, world["cure"]) == []
        assert repo.clinic_ids_for_email(s, "reception@cure.in") == set()
        assert s.get(Clinic, world["demo"]) is not None  # the other clinic untouched
    assert client_as("reception@cure.in").get("/api/me").json()["clinics"] == []
