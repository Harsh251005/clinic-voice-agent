"""Voice & phrases (/api/admin/voice): admins edit the fixed phrases in
English (Hindi suggested, editable), see what is recorded in the current
voice, record takes and play them. A fake voice and a fake OpenAI: never a
vendor."""

import io
from datetime import datetime
import wave

import pytest

from api.dashboard import voice as voice_api
from clinic_agent.config import load_settings
from clinic_agent.providers import hindi
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for
from tests.test_dashboard_api import client_as, world  # noqa: F401 - the fixture
from tests.test_hindi_names import FakeOpenAI
from tests.test_voice_clips import VOICE, FakeVoice

ADMIN = "harsh@example.com"
OK_GREETING = "नमस्ते जी, {clinic} में स्वागत है। मैं ऑटोमेटेड असिस्टेंट हूँ, बातचीत टेक्स्ट में सेव होती है।"


@pytest.fixture
def fake_voice(monkeypatch):
    spoken = FakeVoice()
    monkeypatch.setattr(voice_api, "build_tts", lambda cfg, vendor: spoken)
    monkeypatch.setattr(voice_api, "identity", lambda tts: VOICE)
    return spoken


def _admin():
    return client_as(ADMIN, admin=True)


def _phrase(page, kind, clinic_id=None):
    return next(p for p in page["phrases"] if p["kind"] == kind and p["clinic_id"] == clinic_id)


ROUTES = [
    ("GET", "/api/admin/voice"), ("PUT", "/api/admin/voice/phrases/1"),
    ("PUT", "/api/admin/voice/clinics/{cure}/greeting"), ("DELETE", "/api/admin/voice/clinics/{cure}/greeting"),
    ("POST", "/api/admin/voice/translate"), ("POST", "/api/admin/voice/record"), ("GET", "/api/admin/voice/clips/abc.wav"),
]


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_only_admins(world, method, path):  # noqa: F811
    body = {"source": "x", "text": "x", "english": "x", "takes": [{"phrase_id": 1}]}
    for client in (client_as("reception@cure.in"), client_as()):
        assert client.request(method, path.format(**world), json=body).status_code in (401, 403)


def test_the_page_shows_every_phrase_and_the_greeting_once_per_clinic(world, fake_voice):  # noqa: F811
    page = _admin().get("/api/admin/voice").json()
    assert page["voice"]["voice"] == "v" and page["voice_problem"] == ""
    assert sorted({p["kind"] for p in page["phrases"]}) == ["filler", "goodbye_fallback", "goodbye_time_limit", "greeting"]
    greeting = _phrase(page, "greeting")
    assert "{clinic}" in greeting["text"] and greeting["source"].startswith("Hello")
    assert {t["clinic_id"] for t in greeting["takes"]} == {world["demo"], world["cure"]}
    assert all("{clinic}" not in t["spoken"] and t["recorded_at"] is None for t in greeting["takes"])
    filler = _phrase(page, "filler")
    (take,) = filler["takes"]
    assert take["clinic_id"] is None and take["spoken"] == filler["text"] and take["key"]
    assert {c["name"] for c in page["clinics"]} == {"Demo Family Clinic", "Cure Dental Clinic"}


def test_without_a_voice_the_page_says_why_and_nothing_can_be_recorded(world, env):  # noqa: F811
    env.delenv("SARVAM_API_KEY")
    page = _admin().get("/api/admin/voice").json()
    assert page["voice"] is None and "SARVAM_API_KEY" in page["voice_problem"]
    assert all(t["key"] is None for p in page["phrases"] for t in p["takes"])
    r = _admin().post("/api/admin/voice/record", json={"takes": [{"phrase_id": _phrase(page, "filler")["id"]}]})
    assert r.status_code == 422 and "SARVAM_API_KEY" in r.json()["detail"]


def test_recording_a_take_marks_it_recorded_and_it_plays_as_wav(world, fake_voice):  # noqa: F811
    c = _admin()
    page = c.get("/api/admin/voice").json()
    filler = _phrase(page, "filler")
    r = c.post("/api/admin/voice/record", json={"takes": [{"phrase_id": filler["id"]}]}).json()
    assert r["recorded"] == 1 and r["failed"] == ""
    (take,) = _phrase(r["page"], "filler")["takes"]
    assert take["recorded_at"] and take["duration_s"] == pytest.approx(0.1)
    assert fake_voice.said == [filler["text"]]
    wav = c.get(f"/api/admin/voice/clips/{take['key']}.wav")
    assert wav.headers["content-type"] == "audio/wav"
    with wave.open(io.BytesIO(wav.content)) as w:
        assert (w.getnchannels(), w.getframerate(), w.getnframes()) == (1, 24000, 2400)
    assert c.get("/api/admin/voice/clips/nope.wav").status_code == 404


def test_the_shared_greeting_is_recorded_for_the_clinic_asked_only(world, fake_voice):  # noqa: F811
    c = _admin()
    greeting = _phrase(c.get("/api/admin/voice").json(), "greeting")
    r = c.post("/api/admin/voice/record", json={"takes": [{"phrase_id": greeting["id"], "clinic_id": world["cure"]}]}).json()
    takes = {t["clinic_id"]: t for t in _phrase(r["page"], "greeting")["takes"]}
    assert takes[world["cure"]]["recorded_at"] and takes[world["demo"]]["recorded_at"] is None
    assert fake_voice.said == [takes[world["cure"]]["spoken"]]
    bad = c.post("/api/admin/voice/record", json={"takes": [{"phrase_id": greeting["id"], "clinic_id": 999}]})
    assert bad.status_code == 404


def test_recording_stops_at_the_first_failure_and_says_why(world, fake_voice):  # noqa: F811
    fake_voice.fails = RuntimeError("402 out of credits")
    c = _admin()
    page = c.get("/api/admin/voice").json()
    fillers = [{"phrase_id": p["id"]} for p in page["phrases"] if p["kind"] == "filler"]
    r = c.post("/api/admin/voice/record", json={"takes": fillers}).json()
    assert r["recorded"] == 0 and "RuntimeError" in r["failed"] and len(fake_voice.said) == 1


def test_editing_a_phrase_keeps_its_english_and_says_it_live_until_recorded_again(world, fake_voice):  # noqa: F811
    c = _admin()
    filler = _phrase(c.get("/api/admin/voice").json(), "filler")
    c.post("/api/admin/voice/record", json={"takes": [{"phrase_id": filler["id"]}]})
    page = c.put(f"/api/admin/voice/phrases/{filler['id']}", json={"source": "Wait a moment.", "text": "ज़रा रुकिए।"}).json()
    edited = next(p for p in page["phrases"] if p["id"] == filler["id"])
    assert (edited["source"], edited["text"]) == ("Wait a moment.", "ज़रा रुकिए।")
    assert edited["takes"][0]["recorded_at"] is None  # new words: not recorded yet


def test_a_greeting_that_drops_the_disclosure_is_refused(world, fake_voice):  # noqa: F811
    c = _admin()
    greeting = _phrase(c.get("/api/admin/voice").json(), "greeting")
    r = c.put(f"/api/admin/voice/phrases/{greeting['id']}", json={"source": "Hello", "text": "नमस्ते, {clinic} में स्वागत है।"})
    assert r.status_code == 422 and "automated assistant" in r.json()["detail"]
    r = c.put(f"/api/admin/voice/clinics/{world['cure']}/greeting", json={"source": "Hi", "text": "नमस्ते।"})
    assert r.status_code == 422


def test_a_clinic_can_have_its_own_greeting_and_go_back_to_the_shared_one(world, fake_voice):  # noqa: F811
    c = _admin()
    page = c.put(f"/api/admin/voice/clinics/{world['cure']}/greeting", json={"source": "Hello", "text": OK_GREETING}).json()
    own = _phrase(page, "greeting", world["cure"])
    assert own["clinic_name"] == "Cure Dental Clinic" and [t["clinic_id"] for t in own["takes"]] == [world["cure"]]
    assert [t["clinic_id"] for t in _phrase(page, "greeting")["takes"]] == [world["demo"]]
    assert next(cl for cl in page["clinics"] if cl["id"] == world["cure"])["own_greeting"]
    page = c.delete(f"/api/admin/voice/clinics/{world['cure']}/greeting").json()
    assert not [p for p in page["phrases"] if p["clinic_id"] is not None]
    assert c.delete("/api/admin/voice/clinics/9999/greeting").status_code == 404


@pytest.fixture
def openai_says(env, monkeypatch):
    env.setenv("OPENAI_API_KEY", "sk-test")
    hindi._cache.clear()
    FakeOpenAI.asked = []
    return lambda reply: monkeypatch.setattr(hindi.openai, "OpenAI", FakeOpenAI(reply))


def test_the_hindi_is_suggested_from_the_english_and_its_tokens_counted(world, openai_says):  # noqa: F811
    openai_says("जी, ज़रा रुकिए।")
    r = _admin().post("/api/admin/voice/translate", json={"english": "Yes, please wait."})
    assert r.json() == {"text": "जी, ज़रा रुकिए।"}
    with sessions_for(load_settings().database_url)() as s:
        assert any(u.source == "voice_phrase" for u in repo.usage_between(s, datetime(2000, 1, 1), datetime(2100, 1, 1)))


def test_a_failed_suggestion_says_type_it_yourself_and_tells_the_admin(world, openai_says):  # noqa: F811
    openai_says("not hindi at all")
    r = _admin().post("/api/admin/voice/translate", json={"english": "Yes, please wait."})
    assert r.status_code == 503 and "Type it yourself" in r.json()["detail"]
    with sessions_for(load_settings().database_url)() as s:
        (inc,) = [i for i in repo.open_incidents(s) if i.kind == "phrase_translation_failing"]
        assert "NoSuggestion" in inc.detail
    openai_says("जी, ज़रा रुकिए।")
    _admin().post("/api/admin/voice/translate", json={"english": "Yes, wait."})
    with sessions_for(load_settings().database_url)() as s:
        assert not [i for i in repo.open_incidents(s) if i.kind == "phrase_translation_failing"]
