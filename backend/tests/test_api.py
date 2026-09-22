"""The call-link server: the page, the signed join pass, and its limits."""

import base64
import json

import pytest
from fastapi.testclient import TestClient
from livekit import api as lk

from api.limits import RateLimiter
from clinic_agent.config import ConfigError, load_settings
from clinic_agent.dispatch import AGENT_NAME, clinic_id_from

KEY, SECRET = "APItestkey", "s" * 40


@pytest.fixture
def seeded_url(tmp_path):
    from clinic_agent.store import migrations, repo
    from clinic_agent.store.db import make_engine, session_factory
    from seeds.demo_clinic import seed_demo

    url = f"sqlite:///{tmp_path}/api.db"
    engine = make_engine(url)
    migrations.upgrade(engine)
    with session_factory(engine)() as s:
        seed_demo(s)
        repo.create_clinic(s, name="<script>alert(1)</script> Clinic", slug="evil-name")
    return url


@pytest.fixture
def client(env, seeded_url):
    env.setenv("DATABASE_URL", seeded_url)
    env.setenv("LIVEKIT_URL", "wss://clinic-voice-agent-a35bk4rv.livekit.cloud")
    env.setenv("LIVEKIT_API_KEY", KEY)
    env.setenv("LIVEKIT_API_SECRET", SECRET)
    env.setenv("DASHBOARD_LOGIN", "off")  # call links need no dashboard sign-in
    from api.app import create_app

    return TestClient(create_app(load_settings()))


def _claims(token):
    return lk.TokenVerifier(KEY, SECRET).verify(token)


# ---------- page ----------

def test_call_page_shows_the_clinic(client):
    r = client.get("/call/demo-family-clinic")
    assert r.status_code == 200
    assert "Demo Family Clinic" in r.text and "Borivali East" in r.text
    assert 'href="tel:02212345678"' in r.text
    assert 'data-slug="demo-family-clinic"' in r.text


def test_clinic_details_are_escaped(client):
    r = client.get("/call/evil-name")
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;" in r.text


@pytest.mark.parametrize("slug", ["no-such-clinic", "Demo-Family-Clinic", "a" * 70])
def test_unknown_link_is_a_friendly_404(client, slug):
    r = client.get(f"/call/{slug}")
    assert r.status_code == 404
    assert "This call link doesn't exist" in r.text


def test_security_headers(client):
    r = client.get("/call/demo-family-clinic")
    csp = r.headers["Content-Security-Policy"]
    assert "script-src 'self' https://cdn.jsdelivr.net" in csp
    assert "wss://clinic-voice-agent-a35bk4rv.livekit.cloud" in csp
    assert "wss://*.production.livekit.cloud" in csp  # LiveKit's regional hosts
    assert "frame-ancestors 'none'" in csp
    assert r.headers["Permissions-Policy"] == "microphone=(self), camera=()"


def test_the_livekit_client_is_pinned_with_an_integrity_hash(client):
    r = client.get("/call/demo-family-clinic")
    assert "livekit-client@2.22.3/dist/livekit-client.umd.min.js" in r.text
    assert 'integrity="sha384-' in r.text


# ---------- join pass ----------

def test_pass_dispatches_this_clinics_receptionist(client):
    r = client.post("/call/demo-family-clinic/pass")
    assert r.status_code == 200
    body = r.json()
    assert body["url"] == "wss://clinic-voice-agent-a35bk4rv.livekit.cloud"
    claims = _claims(body["token"])
    (dispatch,) = claims.room_config.agents
    assert dispatch.agent_name == AGENT_NAME
    assert clinic_id_from(dispatch.metadata) == 1


def test_pass_allows_one_private_voice_call(client):
    claims = _claims(client.post("/call/demo-family-clinic/pass").json()["token"])
    assert claims.video.room_join and claims.video.room.startswith("call-demo-family-clinic-")
    assert claims.video.can_publish_sources == ["microphone"]
    assert not claims.video.can_publish_data
    assert not claims.video.room_admin and not claims.video.room_create
    assert claims.room_config.max_participants == 2
    assert claims.identity.startswith("caller-")


def test_every_call_gets_its_own_room(client):
    rooms = {_claims(client.post("/call/demo-family-clinic/pass").json()["token"]).video.room for _ in range(3)}
    assert len(rooms) == 3


def test_a_tampered_pass_is_rejected(client):
    # Pointing the pass at another clinic breaks the signature.
    token = client.post("/call/demo-family-clinic/pass").json()["token"]
    head, payload, sig = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["roomConfig"]["agents"][0]["metadata"] = '{"clinic_id": 2}'
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    with pytest.raises(Exception):
        _claims(f"{head}.{forged}.{sig}")


def test_pass_for_unknown_clinic_is_404(client):
    r = client.post("/call/no-such-clinic/pass")
    assert r.status_code == 404
    assert r.json()["error"] == "This call link doesn't exist."


def test_one_caller_is_rate_limited(client):
    codes = [client.post("/call/demo-family-clinic/pass").status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]
    assert "Too many calls" in client.post("/call/demo-family-clinic/pass").json()["error"]


def test_a_forwarded_ip_header_is_ignored_unless_configured(client):
    # Unconfigured, a caller can't dodge the limit by inventing IPs.
    codes = [
        client.post("/call/demo-family-clinic/pass", headers={"CF-Connecting-IP": f"1.2.3.{i}"}).status_code
        for i in range(6)
    ]
    assert codes[-1] == 429


def test_configured_ip_header_separates_callers_behind_a_tunnel(env, seeded_url):
    env.setenv("DATABASE_URL", seeded_url)
    env.setenv("LIVEKIT_URL", "wss://x.livekit.cloud")
    env.setenv("LIVEKIT_API_KEY", KEY)
    env.setenv("LIVEKIT_API_SECRET", SECRET)
    env.setenv("DASHBOARD_LOGIN", "off")  # call links need no dashboard sign-in
    env.setenv("CLIENT_IP_HEADER", "CF-Connecting-IP")
    from api.app import create_app

    c = TestClient(create_app(load_settings()))
    for i in range(6):  # six different patients, one call each
        assert c.post("/call/demo-family-clinic/pass", headers={"CF-Connecting-IP": f"1.2.3.{i}"}).status_code == 200


def test_health(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_missing_livekit_settings_stop_startup(env, seeded_url):
    env.setenv("DATABASE_URL", seeded_url)
    env.setenv("DASHBOARD_LOGIN", "off")
    from api.app import create_app

    with pytest.raises(ConfigError, match="LIVEKIT_URL is not set"):
        create_app(load_settings())


# ---------- rate limiter ----------

def test_rate_limiter_window_slides():
    now = [0.0]
    limit = RateLimiter(2, 60, clock=lambda: now[0])
    assert limit.allow("a") and limit.allow("a") and not limit.allow("a")
    assert limit.allow("b")  # per key
    now[0] = 61
    assert limit.allow("a")


def test_rate_limiter_forgets_idle_keys():
    now = [0.0]
    limit = RateLimiter(2, 60, clock=lambda: now[0])
    for i in range(100):
        limit.allow(f"ip-{i}")
    now[0] = 200
    limit.allow("new")
    assert set(limit._events) == {"new"}


def test_rate_limiter_is_safe_across_threads():
    from concurrent.futures import ThreadPoolExecutor

    from api.limits import RateLimiter

    limiter = RateLimiter(100, 60)
    with ThreadPoolExecutor(16) as pool:
        allowed = list(pool.map(lambda i: limiter.allow("same-ip"), range(1000)))
    assert allowed.count(True) == 100
