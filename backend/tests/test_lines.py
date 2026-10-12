"""Two language lines, each its own vendors; a line without its keys is off, not fatal."""

import pytest

from clinic_agent.config import load_settings
from clinic_agent.dispatch import LANGUAGES
from clinic_agent.lines import LINES, NAMES, available


def test_every_language_has_exactly_one_line():
    assert tuple(LINES) == LANGUAGES
    assert all(line.language == lang for lang, line in LINES.items())
    assert set(NAMES) == set(LANGUAGES)


def test_english_is_elevenlabs_and_openai_and_hindi_is_sarvam():
    # Harsh's rule (2026-10-12): two separate pipelines, each for its own language.
    en, hi = LINES["en"], LINES["hi"]
    assert (en.stt, en.llm, en.tts) == ("elevenlabs", "openai", "elevenlabs")
    assert (hi.stt, hi.llm, hi.tts) == ("sarvam", "sarvam", "sarvam")


def test_with_every_key_both_lines_are_up(env):
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    assert available(load_settings()) == {"en": None, "hi": None}


@pytest.mark.parametrize(("missing", "off", "key"), [
    ("SARVAM_API_KEY", "hi", "SARVAM_API_KEY"),
    ("OPENAI_API_KEY", "en", "OPENAI_API_KEY"),
    ("ELEVENLABS_API_KEY", "en", "ELEVENLABS_API_KEY"),
])
def test_a_missing_key_turns_off_only_its_line(env, missing, off, key):
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    env.delenv(missing)
    lines = available(load_settings())
    assert key in lines[off]
    assert all(why is None for lang, why in lines.items() if lang != off)


def test_text_only_needs_just_the_llms_key(env):
    env.setenv("OPENAI_API_KEY", "sk-test")  # no ElevenLabs key: text needs no voice
    assert available(load_settings(), text_only=True)["en"] is None
