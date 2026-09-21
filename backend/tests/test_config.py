import dataclasses

import pytest

from clinic_agent.config import ConfigError, load_settings


def test_defaults(env):
    cfg = load_settings()
    assert (cfg.stt_provider, cfg.llm_provider, cfg.tts_provider) == ("sarvam",) * 3
    assert cfg.stt_model == "saaras:v4"
    assert cfg.stt_language == "unknown"
    assert cfg.llm_model == "sarvam-105b-conversations"
    assert cfg.tts_model == "bulbul:v3"
    assert cfg.tts_speaker == "suhani"
    assert cfg.tts_codec == "linear16"
    assert cfg.min_endpointing_delay == 0.2


def test_missing_key_is_a_config_error(env):
    env.delenv("SARVAM_API_KEY")
    with pytest.raises(ConfigError, match="SARVAM_API_KEY is not set"):
        load_settings()


def test_whitespace_key_counts_as_missing(env):
    env.setenv("SARVAM_API_KEY", "   ")
    with pytest.raises(ConfigError):
        load_settings()


def test_env_overrides_default(env):
    env.setenv("TTS_SPEAKER", "priya")
    env.setenv("MIN_ENDPOINTING_DELAY", "0.5")
    cfg = load_settings()
    assert cfg.tts_speaker == "priya"
    assert cfg.min_endpointing_delay == 0.5


def test_blank_value_falls_back_to_default(env):
    env.setenv("TTS_SPEAKER", "")
    assert load_settings().tts_speaker == "suhani"


def test_non_numeric_number_is_a_config_error(env):
    env.setenv("STT_SAMPLE_RATE", "sixteen")
    with pytest.raises(ConfigError, match="STT_SAMPLE_RATE must be a number"):
        load_settings()


def test_settings_are_immutable(env):
    cfg = load_settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.llm_model = "other"
