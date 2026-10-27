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
    for field, other in (("voice", "anushka"), ("model", "bulbul:v2"), ("language_code", "mr-IN"), ("sample_rate", 16000)):
        assert key != clip_key({**voice, field: other}, "नमस्ते"), field
    env.setenv("SARVAM_TTS_MODEL", "bulbul:v4-flash")
    env.setenv("SARVAM_TTS_SPEAKER", "aparna_hi_customer")
    assert key != clip_key(identity(build_tts(load_settings(), "sarvam")), "नमस्ते")  # a new voice


from clinic_agent.store import repo  # noqa: E402
from clinic_agent.voice_clips import load  # noqa: E402

VOICE = {"vendor": "sarvam", "model": "m", "voice": "v", "language_code": "hi-IN", "sample_rate": 24000, "codec": "linear16"}


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
