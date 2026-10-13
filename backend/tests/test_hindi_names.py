"""Names in Hindi, suggested from the English name; staff can change them."""

from types import SimpleNamespace

import openai
import pytest

from clinic_agent.config import ConfigError, load_settings
from clinic_agent.providers import hindi
from tests.test_dashboard_api import client_as, world  # noqa: F401 - fixtures


class FakeOpenAI:
    """openai.OpenAI that answers `reply` (or raises it), and notes what it was asked."""
    asked: list[str] = []

    def __init__(self, reply):
        self.reply = reply

    def __call__(self, **_kwargs):
        def create(**kw):
            FakeOpenAI.asked.append(kw["messages"][-1]["content"])
            if isinstance(self.reply, Exception):
                raise self.reply
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))],
                                   usage=SimpleNamespace(prompt_tokens=120, completion_tokens=9,
                                                         prompt_tokens_details=SimpleNamespace(cached_tokens=20)))
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


@pytest.fixture
def answers(env, monkeypatch):
    env.setenv("OPENAI_API_KEY", "sk-test")
    hindi._cache.clear()
    FakeOpenAI.asked = []

    def set_reply(reply):
        monkeypatch.setattr(hindi.openai, "OpenAI", FakeOpenAI(reply))
    return set_reply


def test_a_name_comes_back_in_devanagari_cleaned(answers):
    answers('  "डॉक्टर  आशा मेहता" ')
    assert hindi.suggest(load_settings(), " Dr. Asha  Mehta ") == "डॉक्टर आशा मेहता"
    assert FakeOpenAI.asked == ["Dr. Asha Mehta"]
    hindi.suggest(load_settings(), "Dr. Asha Mehta")
    assert len(FakeOpenAI.asked) == 1  # the same name is asked for once


@pytest.mark.parametrize("reply", ["Dr. Asha Mehta", "डॉक्टर Asha", "", "क" * 201])
def test_an_answer_that_isnt_a_devanagari_name_is_no_suggestion(answers, reply):
    answers(reply)
    with pytest.raises(hindi.NoSuggestion):
        hindi.suggest(load_settings(), "Dr. Asha Mehta")


def test_a_failed_request_is_no_suggestion_and_no_key_is_a_config_error(answers, env):
    answers(openai.APITimeoutError(request=None))
    with pytest.raises(hindi.NoSuggestion, match="APITimeoutError"):
        hindi.suggest(load_settings(), "Dr. Asha Mehta")
    env.delenv("OPENAI_API_KEY")
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        hindi.suggest(load_settings(), "Dr. Asha Mehta")


def test_staff_get_a_suggestion_while_typing(world, answers):  # noqa: F811
    answers("क्योर डेंटल क्लिनिक")
    r = client_as("reception@cure.in").post(f"/api/clinics/{world['cure']}/hindi-name", json={"name": "Cure Dental Clinic"})
    assert r.json() == {"name_hi": "क्योर डेंटल क्लिनिक"}


def test_saving_with_the_hindi_box_blank_fills_it_in_and_a_typed_one_is_kept(world, answers):  # noqa: F811
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    details = {"name": "Cure Dental", "address": "", "phone": "", "booking_window_days": 30, "slots_offered": 3}
    answers("क्योर डेंटल")
    assert c.patch(base, json=details | {"name_hi": ""}).json()["name_hi"] == "क्योर डेंटल"
    assert c.patch(base, json=details | {"name_hi": "क्यूअर डेंटल"}).json()["name_hi"] == "क्यूअर डेंटल"  # staff's own
    answers("डॉक्टर रोहन")
    doctor = c.post(f"{base}/doctors", json={"name": "Dr. Rohan", "fee": 300, "slot_minutes": 15}).json()
    assert doctor["name_hi"] == "डॉक्टर रोहन"


def test_a_failed_suggestion_never_blocks_a_save_and_is_flagged(world, answers):  # noqa: F811
    answers(openai.APIConnectionError(request=None))
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    r = c.post(f"{base}/doctors", json={"name": "Dr. Rohan", "fee": 300, "slot_minutes": 15})
    assert r.status_code == 200 and r.json()["name_hi"] == ""  # saved; the Hindi line spells it itself
    assert c.post(f"{base}/hindi-name", json={"name": "Dr. Rohan"}).status_code == 503
    titles = [p["title"] for p in client_as("harsh@example.com", admin=True).get("/api/admin/problems").json()["open"]]
    assert any("Hindi name suggestions are failing (NoSuggestion)" in t for t in titles)


def test_words_the_clinic_already_spells_are_spelt_the_same_again(answers):
    known = hindi.glossary([("Dr. Harsh Dharnidharka", "डॉक्टर हर्ष धरनिधरका"), ("Odd Name", "एक")])
    assert known == {"Harsh": "हर्ष", "Dharnidharka": "धरनिधरका"}  # words that don't line up are skipped
    answers("धरनिधरका फ़ैमिली क्लिनिक")
    hindi.suggest(load_settings(), "Dharnidharka Family Clinic", known)
    assert FakeOpenAI.asked == ["Dharnidharka Family Clinic\nSpell these words exactly as the clinic already does: Dharnidharka = धरनिधरका"]


def test_each_suggestion_asked_of_openai_is_counted_in_costs(world, answers):  # noqa: F811
    from datetime import timedelta

    from clinic_agent.store import repo
    from clinic_agent.store.db import sessions_for
    from clinic_agent.store.models import utc_now

    answers("क्योर डेंटल क्लिनिक")
    c = client_as("reception@cure.in")
    for _ in range(2):  # the second answer comes from the cache: nothing spent
        c.post(f"/api/clinics/{world['cure']}/hindi-name", json={"name": "Cure Dental Clinic"})
    with sessions_for(load_settings().database_url)() as s:
        rows = repo.usage_between(s, utc_now() - timedelta(minutes=1), utc_now() + timedelta(minutes=1))
    assert {(u.source, u.part, u.provider, u.model, u.unit, u.quantity, u.clinic_id) for u in rows} == {
        ("hindi_names", "other", "openai", hindi.MODEL, "tokens_in", 100.0, world["cure"]),
        ("hindi_names", "other", "openai", hindi.MODEL, "tokens_cached", 20.0, world["cure"]),
        ("hindi_names", "other", "openai", hindi.MODEL, "tokens_out", 9.0, world["cure"]),
    }
