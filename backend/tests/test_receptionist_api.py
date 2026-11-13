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
    assert page["hindi_llm"] == "openai" and page["greeting_interruptible"] is False  # Harsh, 2026-11-13
    assert page["blank_means"]["openai_llm_model"] == "gpt-4.1-mini"
    assert page["limits"]["interrupt_min_speech"] == {"low": 0.05, "high": 3.0, "default": 0.3}


def test_a_change_saves_only_what_was_sent_and_is_checked(world):  # noqa: F811
    c = client_as(ADMIN, admin=True)
    page = c.put("/api/admin/receptionist", json={"rules": "Be kind at {clinic_name}.", "greeting_interruptible": True}).json()
    assert page["rules"] == "Be kind at {clinic_name}." and page["greeting_interruptible"] is True
    assert page["hindi_llm"] == "openai"  # not sent: unchanged
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


def test_a_speaker_the_voice_model_lacks_is_refused_before_it_breaks_calls(world, env):  # noqa: F811
    # Seen 2026-11-10: bulbul:v4-flash with the default speaker (suhani) can't build: every call would fail.
    # Model and speaker sit side by side per clinic, so both change in one save.
    env.setenv("SARVAM_API_KEY", "sk-test")
    c = client_as(ADMIN, admin=True)
    path = f"/api/admin/clinics/{world['cure']}/receptionist"
    r = c.put(path, json={"tts_model": "bulbul:v4-flash"})
    assert r.status_code == 422 and "suhani" in r.text and r.json()["detail"].startswith("Cure")
    assert c.get(path).json()["tts_model"] == ""  # nothing saved
    ok = c.put(path, json={"tts_model": "bulbul:v4-flash", "tts_speaker": "ritu_hi_medical"})
    assert ok.status_code == 200 and ok.json()["tts_model"] == "bulbul:v4-flash"
    assert c.put(path, json={"tts_speaker": "suhani"}).status_code == 422


def test_a_clinics_voice_is_picked_from_lists_of_womens_voices(world):  # noqa: F811
    # Harsh, 2026-11-12: dropdowns, not typed names; she is always a woman. No voice key needed to check.
    c = client_as(ADMIN, admin=True)
    path = f"/api/admin/clinics/{world['cure']}/receptionist"
    voices = {m["name"]: m for m in c.get(path).json()["voices"]}
    assert list(voices)[0] == "bulbul:v3"  # the default model first
    v3, flash = voices["bulbul:v3"], voices["bulbul:v4-flash"]
    names = [s["name"] for s in v3["speakers"]]
    assert "suhani" in names and "rahul" not in names and v3["default_speaker"] == "suhani"
    assert (v3["pitch"], flash["pitch"]) == (False, True)
    offered = {s["name"]: s["label"] for s in flash["speakers"]}
    assert offered["ritu_hi_customer_warm"] == "Ritu, customer warm"
    assert not {"rahul_hi_conversational", "ritu_en_medical"} & offered.keys()  # a man; not Hindi
    assert flash["default_speaker"] in offered
    for bad in ({"tts_speaker": "rahul"}, {"tts_model": "bulbul:v9"},
                {"tts_model": "bulbul:v4-flash", "tts_speaker": "rahul_hi_conversational"}):
        r = c.put(path, json=bad)
        assert r.status_code == 422 and "list" in r.json()["detail"], bad
    assert c.put(path, json={"tts_speaker": "priya"}).json()["tts_speaker"] == "priya"
    assert c.put(path, json={"tts_speaker": ""}).json()["tts_speaker"] == ""  # back to the default
