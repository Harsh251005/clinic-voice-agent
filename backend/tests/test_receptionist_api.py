"""Admin > Receptionist (Harsh, 2026-11-10): what every clinic's receptionist
shares, read and changed by admins only."""

import pytest

from clinic_agent.prompts import RULES
from tests.test_dashboard_api import client_as, world  # noqa: F401 - the fixture

ADMIN = "harsh@example.com"


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_only_admins(world, method):  # noqa: F811
    for client in (client_as("reception@cure.in"), client_as()):
        assert client.request(method, "/api/admin/receptionist", json={"rules": "x"}).status_code in (401, 403)


def test_the_page_shows_the_settings_with_their_defaults(world):  # noqa: F811
    page = client_as(ADMIN, admin=True).get("/api/admin/receptionist").json()
    assert page["rules"] == "" and page["default_rules"] == RULES["hi"] and page["rules_max_words"] == 500
    assert page["hindi_llm"] == "sarvam" and page["greeting_interruptible"] is False
    assert page["blank_means"]["openai_llm_model"] == "gpt-4.1-mini"
    assert page["limits"]["interrupt_min_speech"] == {"low": 0.05, "high": 3.0, "default": 0.3}


def test_a_change_saves_only_what_was_sent_and_is_checked(world):  # noqa: F811
    c = client_as(ADMIN, admin=True)
    page = c.put("/api/admin/receptionist", json={"rules": "Be kind at {clinic_name}.", "greeting_interruptible": True}).json()
    assert page["rules"] == "Be kind at {clinic_name}." and page["greeting_interruptible"] is True
    assert page["hindi_llm"] == "sarvam"  # not sent: unchanged
    too_long = c.put("/api/admin/receptionist", json={"rules": "word " * 501})
    assert too_long.status_code == 422 and "at most 500" in too_long.text
    assert c.put("/api/admin/receptionist", json={"hindi_llm": "gemini"}).status_code == 422
    assert c.put("/api/admin/receptionist", json={"vad_min_silence": 9}).status_code == 422
    back = c.put("/api/admin/receptionist", json={"rules": ""}).json()  # reset to the default
    assert back["rules"] == ""


# ---------- a clinic's own (slice 4) ----------

@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_a_clinics_receptionist_is_admins_only_even_for_its_own_staff(world, method):  # noqa: F811
    path = f"/api/admin/clinics/{world['cure']}/receptionist"
    for client in (client_as("reception@cure.in"), client_as()):
        assert client.request(method, path, json={"directions": "x"}).status_code in (401, 403)


def test_a_clinics_receptionist_is_read_changed_and_checked(world):  # noqa: F811
    c = client_as(ADMIN, admin=True)
    path = f"/api/admin/clinics/{world['cure']}/receptionist"
    page = c.get(path).json()
    assert page["tts_pace"] == 1.0 and page["tts_pitch"] is None and page["speaker_default"] == "suhani"
    page = c.put(path, json={"instructions": "Parking is free.", "tts_pace": 0.95, "tts_pitch": 0.1}).json()
    assert (page["instructions"], page["tts_pace"], page["tts_pitch"]) == ("Parking is free.", 0.95, 0.1)
    assert c.put(path, json={"tts_pitch": None}).json()["tts_pitch"] is None  # back to the voice's own
    assert c.put(path, json={"tts_pace": 3}).status_code == 422
    assert c.put(path, json={"instructions": "word " * 151}).status_code == 422
    assert c.get("/api/admin/clinics/99999/receptionist").status_code == 404
    other = c.get(f"/api/admin/clinics/{world['demo']}/receptionist").json()
    assert other["instructions"] == ""  # each clinic its own



def test_admins_are_listed_read_only_for_admins(world, env):  # noqa: F811
    env.setenv("ADMIN_EMAILS", "harsh@example.com, Friend@Example.com")
    page = client_as(ADMIN, admin=True).get("/api/admin/admins").json()
    assert page["emails"] == ["friend@example.com", "harsh@example.com"]
    assert client_as("reception@cure.in").get("/api/admin/admins").status_code == 403
    assert client_as(ADMIN, admin=True).put("/api/admin/admins", json={"emails": ["x@y.z"]}).status_code == 405
