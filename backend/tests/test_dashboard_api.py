"""The dashboard API: sign-in, who may touch what, and each screen's actions.

The attack tests matter most: a signed-in member of one clinic must not
read or change another clinic's rows, whatever ids they put in the URL.
"""

from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient

from api.dashboard.access import Viewer, current_viewer
from clinic_agent.config import ConfigError, load_settings
from clinic_agent.store import migrations, repo
from clinic_agent.store.db import make_engine, session_factory
from seeds.demo_clinic import seed_demo

SECRET = "s" * 64
CSRF = {"x-clinic-console": "1"}


@pytest.fixture
def world(tmp_path, env):
    """Two clinics: demo (Asha, Rohan) and Cure Dental (Khushboo), each with
    an FAQ, time off and a booking, so every kind of row exists in both."""
    url = f"sqlite:///{tmp_path}/dash.db"
    engine = make_engine(url)
    migrations.upgrade(engine)
    with session_factory(engine)() as s:
        demo = seed_demo(s)
        cure = repo.create_clinic(s, name="Cure Dental Clinic").id
        khushboo = repo.add_doctor(s, cure, name="Dr. Khushboo", fee=400, slot_minutes=15).id
        repo.set_doctor_hours(s, khushboo, [(d, time(10), time(13)) for d in range(6)])
        repo.add_faq(s, cure, "Parking?", "Yes.")
        repo.add_time_off(s, cure, date(2026, 12, 1), date(2026, 12, 2), reason="Conference")
        repo.book(s, cure, khushboo, datetime(2026, 12, 7, 10, 0), "Harsh", "8928803112")
        repo.add_time_off(s, demo, date(2026, 12, 1), date(2026, 12, 1))
        repo.book(s, demo, repo.get_clinic(s, demo).doctors[0].id, datetime(2026, 12, 7, 10, 0), "Riya", "9820000000")
        repo.add_member(s, cure, "reception@cure.in")
        ids = {
            "demo": demo, "cure": cure, "khushboo": khushboo,
            "demo_doctor": repo.get_clinic(s, demo).doctors[0].id,
            "demo_faq": repo.get_clinic(s, demo).faq[0].id,
            "demo_off": repo.time_off_overlapping(s, demo, date(2026, 12, 1), date(2026, 12, 1))[0].id,
            "demo_appt": repo.appointments_on(s, demo, date(2026, 12, 7))[0].id,
        }
        repo.add_member(s, demo, "doctor@demo.in")
        ids["demo_member"] = repo.list_members(s, demo)[0].id
    env.setenv("DATABASE_URL", url)
    env.setenv("LIVEKIT_URL", "wss://x.livekit.cloud")
    env.setenv("LIVEKIT_API_KEY", "APIkey")
    env.setenv("LIVEKIT_API_SECRET", SECRET)
    env.setenv("DASHBOARD_LOGIN", "google")
    env.setenv("SESSION_SECRET", SECRET)
    env.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
    env.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    env.setenv("ADMIN_EMAILS", "harsh@example.com")
    env.setenv("DASHBOARD_URL", "http://localhost:3000")
    return ids


def client_as(email=None, admin=False):
    """A client whose viewer is set directly (no Google), or signed out."""
    from api.app import create_app

    app = create_app(load_settings())
    if email is not None:
        def viewer():
            with app.state.sessions() as s:
                ids = frozenset(repo.clinic_ids_for_email(s, email))
            return Viewer(email=email, is_admin=admin, clinic_ids=ids)
        app.dependency_overrides[current_viewer] = viewer
    return TestClient(app, headers=CSRF)


# ---------- signing in ----------

def _google_says(monkeypatch, **userinfo):
    async def fake(self, request, **kwargs):
        return {"userinfo": userinfo}
    monkeypatch.setattr(
        "authlib.integrations.starlette_client.StarletteOAuth2App.authorize_access_token", fake
    )


def test_signed_out_is_401(world):
    assert client_as().get("/api/me").status_code == 401


def test_google_sign_in_sets_a_session_and_sign_out_clears_it(world, monkeypatch):
    _google_says(monkeypatch, email="Reception@Cure.in", email_verified=True)
    c = client_as()
    r = c.get("/api/auth/callback", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "http://localhost:3000/"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    me = c.get("/api/me").json()
    assert me == {"email": "reception@cure.in", "is_admin": False, "login": "google",
                  "clinics": [{"id": world["cure"], "name": "Cure Dental Clinic", "slug": "cure-dental-clinic"}]}
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/me").status_code == 401


def test_unverified_google_email_gets_no_session(world, monkeypatch):
    _google_says(monkeypatch, email="reception@cure.in", email_verified=False)
    c = client_as()
    r = c.get("/api/auth/callback", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:3000/?signin=unverified"
    assert c.get("/api/me").status_code == 401


def test_sign_in_is_redirected_to_google_with_our_callback(world):
    c = client_as()
    from authlib.integrations.starlette_client import StarletteOAuth2App

    async def metadata(self):
        return {"authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth"}
    import unittest.mock as m
    with m.patch.object(StarletteOAuth2App, "load_server_metadata", metadata):
        r = c.get("/api/auth/login", follow_redirects=False)
    assert r.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fapi%2Fauth%2Fcallback" in r.headers["location"]


def test_a_removed_member_loses_access_at_once(world):
    c = client_as("reception@cure.in")
    assert c.get(f"/api/clinics/{world['cure']}").status_code == 200
    admin = client_as("harsh@example.com", admin=True)
    member_id = admin.get(f"/api/clinics/{world['cure']}/members").json()[0]["id"]
    admin.delete(f"/api/clinics/{world['cure']}/members/{member_id}")
    assert c.get(f"/api/clinics/{world['cure']}").status_code == 404


def test_changes_need_the_csrf_header(world):
    from api.app import create_app

    app = create_app(load_settings())
    app.dependency_overrides[current_viewer] = lambda: Viewer("harsh@example.com", True, frozenset())
    bare = TestClient(app)  # no x-clinic-console header, like a cross-site form
    r = bare.post(f"/api/clinics/{world['cure']}/faq", json={"question": "Q", "answer": "A"})
    assert r.status_code == 403
    assert bare.get(f"/api/clinics/{world['cure']}").status_code == 200  # reading is fine


def test_startup_refuses_missing_or_weak_session_secret(world, env):
    from api.app import create_app

    env.setenv("SESSION_SECRET", "")
    with pytest.raises(ConfigError, match="SESSION_SECRET is not set"):
        create_app(load_settings())
    env.setenv("SESSION_SECRET", "short")
    with pytest.raises(ConfigError, match="too short"):
        create_app(load_settings())


def test_sign_in_off_is_an_admin_with_no_email(world, env):
    env.setenv("DASHBOARD_LOGIN", "off")
    me = client_as().get("/api/me").json()
    assert me["email"] == "" and me["is_admin"] and me["login"] == "off" and len(me["clinics"]) == 2


# ---------- who may open what ----------

def test_member_sees_only_their_clinic(world):
    c = client_as("reception@cure.in")
    assert [x["name"] for x in c.get("/api/me").json()["clinics"]] == ["Cure Dental Clinic"]
    assert c.get(f"/api/clinics/{world['cure']}").status_code == 200
    assert c.get(f"/api/clinics/{world['demo']}").status_code == 404


def test_only_admins_create_clinics_and_manage_teams(world):
    c = client_as("reception@cure.in")
    assert c.post("/api/clinics", json={"name": "Mine"}).status_code == 403
    assert c.get(f"/api/clinics/{world['cure']}/members").status_code == 403
    assert c.post(f"/api/clinics/{world['cure']}/members", json={"email": "x@y.in"}).status_code == 403


ATTACKS = [
    # (method, path under the attacker's own clinic, body, the row it targets)
    ("DELETE", "/faq/{demo_faq}", None),
    ("DELETE", "/time-off/{demo_off}", None),
    ("PATCH", "/doctors/{demo_doctor}", {"fee": 1}),
    ("PUT", "/doctors/{demo_doctor}/hours", {"sittings": []}),
    ("POST", "/appointments/{demo_appt}/cancel", None),
    ("POST", "/time-off", {"date_from": "2026-12-01", "date_to": "2026-12-01", "doctor_id": "{demo_doctor}"}),
]


@pytest.mark.parametrize(("method", "path", "body"), ATTACKS)
def test_another_clinics_rows_cant_be_reached_through_your_own_clinic(world, method, path, body):
    c = client_as("reception@cure.in")
    fill = lambda v: int(v.format(**world)) if isinstance(v, str) and v.startswith("{") else v  # noqa: E731
    body = {k: fill(v) for k, v in body.items()} if body else None
    r = c.request(method, f"/api/clinics/{world['cure']}" + path.format(**world), json=body)
    assert r.status_code == 404
    _demo_untouched(world)


@pytest.mark.parametrize(("method", "path", "body"), ATTACKS[:5])
def test_another_clinics_rows_cant_be_reached_through_its_url(world, method, path, body):
    c = client_as("reception@cure.in")
    r = c.request(method, f"/api/clinics/{world['demo']}" + path.format(**world), json=body)
    assert r.status_code == 404
    _demo_untouched(world)


def test_admin_cant_remove_a_member_through_the_wrong_clinic(world):
    c = client_as("harsh@example.com", admin=True)
    assert c.delete(f"/api/clinics/{world['cure']}/members/{world['demo_member']}").status_code == 404
    assert len(c.get(f"/api/clinics/{world['demo']}/members").json()) == 1


def _demo_untouched(world):
    admin = client_as("harsh@example.com", admin=True)
    demo = admin.get(f"/api/clinics/{world['demo']}").json()
    assert any(f["id"] == world["demo_faq"] for f in demo["faq"])
    assert any(t["id"] == world["demo_off"] for t in demo["time_off"])
    doctor = next(d for d in demo["doctors"] if d["id"] == world["demo_doctor"])
    assert doctor["fee"] == 500 and doctor["hours"]
    appts = admin.get(f"/api/clinics/{world['demo']}/appointments", params={"day": "2026-12-07"}).json()
    assert appts["appointments"][0]["status"] == "booked"


# ---------- each screen's actions ----------

def test_clinic_page_data(world):
    c = client_as("reception@cure.in")
    clinic = c.get(f"/api/clinics/{world['cure']}").json()
    assert clinic["call_link"] == "http://localhost:8080/call/cure-dental-clinic"
    (doctor,) = clinic["doctors"]
    assert doctor["hours_text"] == "Monday to Saturday 10:00-13:00; Sunday not available"
    assert clinic["faq"][0]["question"] == "Parking?"


def test_editing_details_and_link_name(world):
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    r = c.patch(base, json={"name": " Cure Dental ", "address": "Borivali", "phone": "022",
                            "booking_window_days": 14, "slots_offered": 2})
    assert r.json()["name"] == "Cure Dental" and r.json()["booking_window_days"] == 14
    assert c.put(f"{base}/slug", json={"slug": "Cure-Dental"}).json()["slug"] == "cure-dental"
    bad = c.put(f"{base}/slug", json={"slug": "no spaces"})
    assert bad.status_code == 422 and "3-60 characters" in bad.json()["detail"]
    taken = c.put(f"{base}/slug", json={"slug": "demo-family-clinic"})
    assert taken.status_code == 422 and "already taken" in taken.json()["detail"]


def test_adding_a_doctor_with_a_pattern_then_editing_hours(world):
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    pattern = next(p for p in c.get("/api/hours/patterns").json() if p["name"] == "Mon–Sat, 10 am–1 pm and 5–8 pm")
    doctor = c.post(f"{base}/doctors", json={"name": "Dr. Neha", "fee": 600, "slot_minutes": 20,
                                             "hours": pattern["sittings"]}).json()
    assert len(doctor["hours"]) == 12
    assert doctor["hours_text"] == "Monday to Saturday 10:00-13:00 and 17:00-20:00; Sunday not available"
    sunday = [{"weekday": 6, "start": "09:00", "end": "12:00"}]
    assert c.put(f"{base}/doctors/{doctor['id']}/hours", json={"sittings": sunday}).json()["hours_text"] == (
        "Monday to Saturday not available; Sunday 09:00-12:00")
    assert c.patch(f"{base}/doctors/{doctor['id']}", json={"active": False}).json()["active"] is False


def test_bad_hours_are_explained_and_add_nobody(world):
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    overlap = [{"weekday": 1, "start": "10:00", "end": "13:00"}, {"weekday": 1, "start": "12:00", "end": "15:00"}]
    r = c.post(f"{base}/doctors", json={"name": "Dr. Overlap", "fee": 0, "slot_minutes": 15, "hours": overlap})
    assert r.status_code == 422 and "sittings on Tuesday overlap" in r.json()["detail"]
    assert [d["name"] for d in c.get(base).json()["doctors"]] == ["Dr. Khushboo"]


def test_preview_describes_unsaved_hours(world):
    c = client_as("reception@cure.in")
    r = c.post("/api/hours/preview", json={"sittings": [{"weekday": 0, "start": "10:00", "end": "13:00"}]})
    assert r.json()["text"] == "Monday 10:00-13:00; Tuesday to Sunday not available"


def test_faq_and_time_off(world):
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    faq = c.post(f"{base}/faq", json={"question": "UPI?", "answer": "Yes."}).json()
    off = c.post(f"{base}/time-off", json={"date_from": "2026-12-10", "date_to": "2026-12-12",
                                           "doctor_id": world["khushboo"], "reason": "Leave"}).json()
    backwards = c.post(f"{base}/time-off", json={"date_from": "2026-12-12", "date_to": "2026-12-10"})
    assert backwards.status_code == 422
    assert c.delete(f"{base}/faq/{faq['id']}").status_code == 200
    assert c.delete(f"{base}/time-off/{off['id']}").status_code == 200
    clinic = c.get(base).json()
    assert [f["question"] for f in clinic["faq"]] == ["Parking?"]


def test_appointments_by_day_and_cancelling(world):
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    day = c.get(f"{base}/appointments", params={"day": "2026-12-07"}).json()
    assert (day["booked"], day["booked_on_calls"], day["next_7_days"]) == (1, 1, 1)
    (appt,) = day["appointments"]
    assert (appt["patient_name"], appt["doctor_name"], appt["source"]) == ("Harsh", "Dr. Khushboo", "voice")
    assert c.post(f"{base}/appointments/{appt['id']}/cancel").json()["status"] == "cancelled"
    assert c.get(f"{base}/appointments", params={"day": "2026-12-07"}).json()["booked"] == 0
    shown = c.get(f"{base}/appointments", params={"day": "2026-12-07", "include_cancelled": True}).json()
    assert shown["appointments"][0]["status"] == "cancelled"


def test_team_management(world):
    c = client_as("harsh@example.com", admin=True)
    base = f"/api/clinics/{world['cure']}/members"
    assert c.post(base, json={"email": " New@Cure.in "}).json()["email"] == "new@cure.in"
    bad = c.post(base, json={"email": "not-an-email"})
    assert bad.status_code == 422 and "doesn't look like an email" in bad.json()["detail"]
    assert sorted(m["email"] for m in c.get(base).json()) == ["new@cure.in", "reception@cure.in"]


def test_admin_creates_a_clinic(world):
    c = client_as("harsh@example.com", admin=True)
    new = c.post("/api/clinics", json={"name": "Sharma Skin Clinic"}).json()
    assert new["slug"] == "sharma-skin-clinic"
    assert "Sharma Skin Clinic" in [x["name"] for x in c.get("/api/me").json()["clinics"]]
