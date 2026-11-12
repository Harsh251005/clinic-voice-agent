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
    doctor = c.post(f"{base}/doctors", json={"name": "Dr. Rohan", "specialty": "Paediatrician", "fee": 300, "slot_minutes": 15}).json()
    assert doctor["name_hi"] == "डॉक्टर रोहन"


def test_a_rename_writes_the_hindi_name_again_unless_staff_wrote_their_own(world, answers):  # noqa: F811
    # Harsh, 2026-11-12: "Dr. Asha Mehta" renamed "Dr. Asha Shah" kept being called मेहता on calls.
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    answers("डॉक्टर आशा मेहता")
    doctor = c.post(f"{base}/doctors", json={"name": "Dr. Asha Mehta", "specialty": "Dentist", "fee": 300, "slot_minutes": 15}).json()
    url = f"{base}/doctors/{doctor['id']}"
    answers("डॉक्टर आशा शाह")
    # the form sends the Hindi box as it was: the new English name rewrites it
    assert c.patch(url, json={"name": "Dr. Asha Shah", "name_hi": "डॉक्टर आशा मेहता"}).json()["name_hi"] == "डॉक्टर आशा शाह"
    assert c.patch(url, json={"name": "Dr. Asha S. Shah"}).json()["name_hi"] == "डॉक्टर आशा शाह"  # asked again, same answer
    asked = len(FakeOpenAI.asked)
    assert c.patch(url, json={"fee": 400, "name": "Dr. Asha S. Shah", "name_hi": "डॉक्टर आशा शाह"}).json()["name_hi"] == "डॉक्टर आशा शाह"
    assert len(FakeOpenAI.asked) == asked  # nothing renamed: nobody asked
    # renamed and the Hindi changed by staff in the same save: theirs is kept
    assert c.patch(url, json={"name": "Dr. Asha Rao", "name_hi": "डॉक्टर आशा राव जी"}).json()["name_hi"] == "डॉक्टर आशा राव जी"

    details = {"name": "Cure Dental", "address": "", "phone": "", "booking_window_days": 30, "slots_offered": 3}
    assert c.patch(base, json=details | {"name_hi": "क्योर डेंटल"}).json()["name_hi"] == "क्योर डेंटल"
    answers("स्माइल डेंटल")
    assert c.patch(base, json=details | {"name": "Smile Dental", "name_hi": "क्योर डेंटल"}).json()["name_hi"] == "स्माइल डेंटल"


def test_a_rename_that_gets_no_suggestion_drops_the_old_hindi_name(world, answers):  # noqa: F811
    # The old name would be the wrong one to say: blank, the Hindi line spells the new name itself.
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    answers("डॉक्टर आशा मेहता")
    doctor = c.post(f"{base}/doctors", json={"name": "Dr. Asha Mehta", "specialty": "Dentist", "fee": 300, "slot_minutes": 15}).json()
    answers(openai.APIConnectionError(request=None))
    r = c.patch(f"{base}/doctors/{doctor['id']}", json={"name": "Dr. Asha Shah", "name_hi": "डॉक्टर आशा मेहता"})
    assert r.status_code == 200 and r.json()["name"] == "Dr. Asha Shah" and r.json()["name_hi"] == ""


def test_a_failed_suggestion_never_blocks_a_save_and_is_flagged(world, answers):  # noqa: F811
    answers(openai.APIConnectionError(request=None))
    c = client_as("reception@cure.in")
    base = f"/api/clinics/{world['cure']}"
    r = c.post(f"{base}/doctors", json={"name": "Dr. Rohan", "specialty": "Paediatrician", "fee": 300, "slot_minutes": 15})
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


# ---------- the receptionist's fixed phrases (voice clips) ----------

def test_a_phrase_comes_back_in_hindi_with_its_placeholder(answers):
    answers("नमस्ते जी, {clinic} में आपका स्वागत है।")
    english = "Hello, welcome to  {clinic}."
    assert hindi.translate_phrase(load_settings(), english) == "नमस्ते जी, {clinic} में आपका स्वागत है।"
    assert FakeOpenAI.asked == ["Hello, welcome to {clinic}."]
    hindi.translate_phrase(load_settings(), english)
    assert len(FakeOpenAI.asked) == 1  # asked once


def test_a_phrase_and_a_name_with_the_same_words_are_asked_separately(answers):
    answers("जी")
    hindi.translate_phrase(load_settings(), "Yes")
    hindi.suggest(load_settings(), "Yes")
    assert len(FakeOpenAI.asked) == 2  # different instructions: never one answer for both


@pytest.mark.parametrize("reply", [
    "नमस्ते जी, आपका स्वागत है।",             # the placeholder was dropped
    "नमस्ते जी, {clinic} {clinic} में।",      # or doubled
    "नमस्ते जी, {क्लिनिक} में स्वागत है।",      # or translated
    "Namaste ji, {clinic} mein swagat hai",  # Roman letters: the voice can't say them
    "नमस्ते, welcome to {clinic}",
    "{clinic}",
])
def test_a_phrase_that_lost_its_placeholder_or_is_not_devanagari_is_refused(answers, reply):
    answers(reply)
    with pytest.raises(hindi.NoSuggestion):
        hindi.translate_phrase(load_settings(), "Hello, welcome to {clinic}.")


def test_a_phrase_uses_the_clinics_own_spellings_and_reports_usage(answers):
    answers("डॉक्टर हर्ष अभी क्लिनिक में हैं।")
    seen = []
    hindi.translate_phrase(load_settings(), "Dr. Harsh is in the clinic.",
                           known={"Harsh": "हर्ष", "Mehta": "मेहता"}, on_usage=lambda *a: seen.append(a))
    assert FakeOpenAI.asked == ["Dr. Harsh is in the clinic.\nSpell these words exactly as the clinic already does: Harsh = हर्ष"]
    assert seen == [("gpt-4.1-mini", 120, 20, 9)]


def test_the_phrase_instructions_keep_her_feminine_and_the_caller_unassumed():
    rules = hindi.PHRASE_INSTRUCTIONS
    assert "She is a woman" in rules and "never masculine" in rules
    assert "never assuming their gender" in rules and "{clinic} exactly as written" in rules
