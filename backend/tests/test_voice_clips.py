"""Recorded phrases: which recording belongs to which voice and text."""

import pytest

from clinic_agent.config import load_settings
from clinic_agent.providers import build_tts, identity
from clinic_agent.voice_clips import clip_key


def test_the_voice_identity_is_read_from_what_was_built(env):
    sarvam = identity(build_tts(load_settings(), "sarvam"))
    assert sarvam["vendor"] == "sarvam" and sarvam["language_code"] == "hi-IN" and sarvam["codec"] == "linear16"
    with pytest.raises(TypeError):
        identity(object())


def test_a_clip_is_found_again_only_for_the_same_voice_and_exact_text(env):
    voice = identity(build_tts(load_settings(), "sarvam"))
    key = clip_key(voice, "नमस्ते")
    assert key == clip_key(dict(voice), "नमस्ते") and len(key) == 64
    assert key != clip_key(voice, "नमस्ते।")  # one character
    for field, other in (("voice", "anushka"), ("model", "bulbul:v2"), ("language_code", "mr-IN"), ("sample_rate", 16000),
                         ("pace", 1.1), ("pitch", 0.1)):
        assert key != clip_key({**voice, field: other}, "नमस्ते"), field
    env.setenv("SARVAM_TTS_MODEL", "bulbul:v4-flash")
    env.setenv("SARVAM_TTS_SPEAKER", "aparna_hi_customer")
    assert key != clip_key(identity(build_tts(load_settings(), "sarvam")), "नमस्ते")  # a new voice


from clinic_agent.store import repo  # noqa: E402
from clinic_agent.voice_clips import load  # noqa: E402

VOICE = {"vendor": "sarvam", "model": "m", "voice": "v", "language_code": "hi-IN", "sample_rate": 24000, "codec": "linear16",
         "pace": 1.0, "pitch": 0.0}


def _record(s, text, pcm=b"\x01\x02"):
    repo.save_clip(s, key=clip_key(VOICE, text), vendor="sarvam", model="m", voice="v", language_code="hi-IN",
                   sample_rate=24000, text=text, pcm=pcm, duration_s=1.0)


def test_a_phrase_plays_its_recording_only_while_the_voice_and_text_match(db):
    s, clinic_id = db
    clinic = repo.get_clinic(s, clinic_id)
    book = load(s, clinic, ["hi"], lambda language: VOICE)
    live = book.one("greeting", "hi")
    assert live.pcm is None  # not recorded: said live
    assert (clinic.name_hi or clinic.name) in live.text and "{clinic}" not in live.text
    _record(s, live.text)
    recorded = load(s, clinic, ["hi"], lambda language: VOICE).one("greeting", "hi")
    assert recorded.pcm == b"\x01\x02" and recorded.sample_rate == 24000 and recorded.text == live.text
    other = {**VOICE, "voice": "someone else"}
    assert load(s, clinic, ["hi"], lambda language: other).one("greeting", "hi").pcm is None
    repo.set_greeting_override(s, clinic_id, "hi", "बिल्कुल नया।")  # edited text: back to live
    assert load(s, clinic, ["hi"], lambda language: VOICE).one("greeting", "hi").pcm is None


def test_fillers_are_random_and_never_the_same_twice_running(db):
    s, clinic_id = db
    book = load(s, repo.get_clinic(s, clinic_id), ["hi"], lambda language: VOICE)
    said = [book.one("filler", "hi").text for _ in range(30)]
    assert len(set(said)) == 3 and all(a != b for a, b in zip(said, said[1:]))


# ---------- recording (a fake voice: never Sarvam) ----------

import asyncio  # noqa: E402

from livekit import rtc  # noqa: E402

from api.dashboard.problems import admin_words  # noqa: E402
from clinic_agent import voice_clips  # noqa: E402
from clinic_agent.store import migrations  # noqa: E402
from clinic_agent.store.db import make_engine, session_factory  # noqa: E402


class FakeVoice:
    """A TTS whose synthesis gives `samples` of audio, or raises `fails`, or hangs."""

    def __init__(self, samples=2400, fails=None, hangs=False, channels=1):
        self.samples, self.fails, self.hangs, self.channels, self.said = samples, fails, hangs, channels, []

    def synthesize(self, text):
        self.said.append(text)
        voice = self

        class Stream:
            async def collect(self):
                if voice.hangs:
                    await asyncio.sleep(10)
                if voice.fails:
                    raise voice.fails
                return rtc.AudioFrame.create(24000, voice.channels, voice.samples)
        return Stream()


@pytest.fixture
def sessions(tmp_path):
    # A file: record() writes from a worker thread, and SQLite :memory: is per thread.
    engine = make_engine(f"sqlite:///{tmp_path}/clips.db")
    migrations.upgrade(engine)
    yield session_factory(engine)
    engine.dispose()


async def test_a_recording_is_kept_under_its_key_and_its_characters_are_costed(sessions):
    voice = FakeVoice()
    await voice_clips.record(sessions, voice, VOICE, "नमस्ते जी।")
    with sessions() as s:
        clip = repo.clips_by_key(s, [clip_key(VOICE, "नमस्ते जी।")])[clip_key(VOICE, "नमस्ते जी।")]
        assert (clip.sample_rate, len(clip.pcm), clip.duration_s) == (24000, 4800, 0.1)
        (used,) = [u for u in repo.usage_between(s, clip.recorded_at.replace(year=2000), clip.recorded_at.replace(year=3000))]
        assert (used.source, used.part, used.provider, used.model, used.unit, used.quantity) == \
            ("voice_clip", "other", "sarvam", "m", "characters", float(len("नमस्ते जी।")))
    assert voice.said == ["नमस्ते जी।"]


@pytest.mark.parametrize("voice", [
    FakeVoice(fails=RuntimeError("402 Payment Required")),
    FakeVoice(samples=0),
    FakeVoice(channels=2),
], ids=["vendor error", "no audio", "not mono"])
async def test_a_failed_recording_saves_nothing_and_tells_the_admin(sessions, voice):
    with pytest.raises(voice_clips.RecordFailed, match="Calls say it live meanwhile"):
        await voice_clips.record(sessions, voice, VOICE, "नमस्ते जी।")
    with sessions() as s:
        assert not repo.list_clips(s)
        assert not repo.usage_between(s, repo.utc_now().replace(year=2000), repo.utc_now().replace(year=3000))
        (inc,) = [i for i in repo.open_incidents(s) if i.kind == "voice_clip_failed"]
        title, action, _ = admin_words(inc, None)
        assert "Recording a voice clip failed" in title and "Calls say those phrases live" in action


async def test_a_recording_that_hangs_gives_up_and_a_good_one_closes_the_problem(sessions, monkeypatch):
    monkeypatch.setattr(voice_clips, "RECORD_TIMEOUT", 0.05)
    with pytest.raises(voice_clips.RecordFailed, match="took too long"):
        await voice_clips.record(sessions, FakeVoice(hangs=True), VOICE, "जी।")
    await voice_clips.record(sessions, FakeVoice(), VOICE, "जी।")
    with sessions() as s:
        assert not [i for i in repo.open_incidents(s) if i.kind == "voice_clip_failed"]
