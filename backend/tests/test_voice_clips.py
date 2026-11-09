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


# ---------- on calls: recordings when they can play, live words otherwise ----------

from types import SimpleNamespace  # noqa: E402

from clinic_agent.voice_clips import BUILT_IN, Phrasebook, Said, for_call, say  # noqa: E402


def test_the_built_in_words_are_the_seeded_ones():
    # A kind missing from the database is said in these: they must match migration 0014.
    from importlib import import_module

    seeds = import_module("clinic_agent.store.alembic.versions.0014_fixed_phrases_and_their_recordings").SEEDS
    seeded: dict = {}
    for kind, language, _slot, source, text in sorted(seeds, key=lambda r: r[2]):
        seeded.setdefault((kind, language), []).append(text or source)
    assert seeded == BUILT_IN


def test_every_greeting_says_the_call_is_automated_and_saved_as_text():
    # Callers must know they aren't talking to a person, and that the call is kept as text.
    (greeting,) = BUILT_IN[("greeting", "hi")]
    assert "ऑटोमेटेड असिस्टेंट" in greeting and "टेक्स्ट में सेव" in greeting


def test_a_kind_the_database_lacks_is_said_live_in_its_built_in_words(db):
    s, clinic_id = db
    clinic = repo.get_clinic(s, clinic_id)
    for phrase in repo.phrases_for_call(s, clinic_id, "hi"):
        if phrase.kind == "goodbye_time_limit":
            s.delete(phrase)
    s.commit()
    book = load(s, clinic, ["hi"], lambda language: VOICE)
    assert book.one("goodbye_time_limit", "hi") == Said(BUILT_IN[("goodbye_time_limit", "hi")][0])
    greeting = Phrasebook(clinic_name="डेमो क्लिनिक").one("greeting", "hi")
    assert "डेमो क्लिनिक में आपका स्वागत है" in greeting.text and greeting.pcm is None


def test_an_unplayable_recording_is_skipped_and_said_live(db):
    s, clinic_id = db
    clinic = repo.get_clinic(s, clinic_id)
    text = load(s, clinic, ["hi"], lambda language: VOICE).one("greeting", "hi").text
    _record(s, text, pcm=b"\x01")  # half a sample
    assert load(s, clinic, ["hi"], lambda language: VOICE).one("greeting", "hi") == Said(text)


def test_a_typed_console_call_loads_no_recordings(db):
    s, clinic_id = db
    clinic = repo.get_clinic(s, clinic_id)
    text = load(s, clinic, ["hi"], lambda language: VOICE).one("greeting", "hi").text
    _record(s, text)
    assert load(s, clinic, ["hi"], lambda language: None).one("greeting", "hi") == Said(text)


def test_a_call_whose_phrases_cannot_be_read_says_them_live_and_tells_the_admin(sessions, monkeypatch):
    from seeds.demo_clinic import seed_demo

    with sessions() as s:
        clinic = repo.get_clinic(s, seed_demo(s))
        s.expunge(clinic)

    def broken(*args):
        raise RuntimeError("database gone")

    real = voice_clips.load
    monkeypatch.setattr(voice_clips, "load", broken)
    book = for_call(sessions, clinic, "hi", None)
    greeting = book.one("greeting", "hi")
    assert greeting.text == BUILT_IN[("greeting", "hi")][0].replace("{clinic}", clinic.name_hi or clinic.name)
    assert greeting.pcm is None and book.one("filler", "hi").pcm is None
    with sessions() as s:
        (inc,) = [i for i in repo.open_incidents(s) if i.kind == "voice_clips_unread"]
        assert inc.clinic_id == clinic.id and inc.detail == "RuntimeError"
        assert "could not read its fixed phrases" in admin_words(inc, "Demo")[0]
    monkeypatch.setattr(voice_clips, "load", real)
    for_call(sessions, clinic, "hi", None)  # the next call reads them fine: the problem closes as fixed
    with sessions() as s:
        assert not [i for i in repo.open_incidents(s) if i.kind == "voice_clips_unread"]


def test_for_call_finds_the_recordings_of_the_calls_own_voice(sessions, env):
    from clinic_agent.config import load_settings as settings

    from seeds.demo_clinic import seed_demo

    voice = build_tts(settings(), "sarvam")
    with sessions() as s:
        clinic = repo.get_clinic(s, seed_demo(s))
        s.expunge(clinic)
        text = load(s, clinic, ["hi"], lambda language: None).one("greeting", "hi").text
        repo.save_clip(s, key=clip_key(identity(voice), text), vendor="sarvam", model="m", voice="v", language_code="hi-IN",
                       sample_rate=24000, text=text, pcm=b"\x00\x00" * 10, duration_s=0.1)
    assert for_call(sessions, clinic, "hi", voice).one("greeting", "hi").pcm == b"\x00\x00" * 10


class SaySession:
    def __init__(self):
        self.said = []

    def say(self, text, **kwargs):
        self.said.append((text, kwargs))


async def test_a_recorded_phrase_plays_its_audio_and_an_unrecorded_one_is_said_live():
    session = SaySession()
    pcm = bytes(range(256)) * 25  # 6,400 bytes = 3,200 samples at 24 kHz: two 100 ms frames
    say(session, Said("जी, बस एक सेकंड।", pcm, 24000), add_to_chat_ctx=False)
    say(session, Said("नमस्ते"), allow_interruptions=False)
    (text, kwargs), (live_text, live_kwargs) = session.said
    frames = [f async for f in kwargs.pop("audio")]
    assert text == "जी, बस एक सेकंड।" and kwargs == {"add_to_chat_ctx": False}
    assert [f.samples_per_channel for f in frames] == [2400, 800] and all(f.sample_rate == 24000 for f in frames)
    assert b"".join(bytes(f.data) for f in frames) == pcm
    assert (live_text, live_kwargs) == ("नमस्ते", {"allow_interruptions": False})
