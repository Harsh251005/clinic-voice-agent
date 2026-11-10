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
