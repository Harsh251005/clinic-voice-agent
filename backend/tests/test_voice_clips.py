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
