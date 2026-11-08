"""One language line, Hindi: Sarvam ears and voice, its brain set by HINDI_LLM.
A line without its keys is off, said in one line, never a crash."""

import pytest

from clinic_agent.config import ConfigError, load_settings
from clinic_agent.dispatch import LANGUAGES
from clinic_agent.lines import NAMES, available, line_for


def test_hindi_is_the_only_line():
    # Harsh (2026-11-08): Hindi first; the English line and its vendor are gone.
    assert LANGUAGES == ("hi",)
    assert NAMES == {"hi": "Hindi"}


def test_hindi_is_sarvam_with_sarvams_brain_by_default(env):
    line = line_for(load_settings(), "hi")
    assert (line.language, line.stt, line.llm, line.tts) == ("hi", "sarvam", "sarvam", "sarvam")


def test_hindi_llm_openai_swaps_only_the_brain(env):
    # Kept to compare OpenAI's replies with Sarvam's on the same line (Harsh, 2026-11-08).
    env.setenv("HINDI_LLM", "OpenAI")
    line = line_for(load_settings(), "hi")
    assert (line.stt, line.llm, line.tts) == ("sarvam", "openai", "sarvam")


def test_hindi_llm_must_be_sarvam_or_openai(env):
    env.setenv("HINDI_LLM", "gemini")
    with pytest.raises(ConfigError, match="HINDI_LLM must be one of sarvam, openai, got 'gemini'"):
        load_settings()


def test_with_its_key_the_line_is_up(env):
    assert available(load_settings()) == {"hi": None}


def test_without_its_key_the_line_is_off_and_says_why(env):
    env.delenv("SARVAM_API_KEY")
    assert "SARVAM_API_KEY" in available(load_settings())["hi"]


def test_openai_brain_needs_the_openai_key_too(env):
    env.setenv("HINDI_LLM", "openai")
    assert "OPENAI_API_KEY" in available(load_settings())["hi"]
    env.setenv("OPENAI_API_KEY", "sk-test")
    assert available(load_settings()) == {"hi": None}


def test_text_only_needs_just_the_llms_key(env):
    env.setenv("HINDI_LLM", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.delenv("SARVAM_API_KEY")  # text needs no ears or voice
    assert available(load_settings(), text_only=True)["hi"] is None
