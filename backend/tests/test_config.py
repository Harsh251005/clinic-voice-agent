import dataclasses

import pytest

from clinic_agent.config import ConfigError, load_settings


def test_defaults(env):
    cfg = load_settings()
    assert (cfg.stt_provider, cfg.llm_provider, cfg.tts_provider) == ("sarvam",) * 3
    assert cfg.min_endpointing_delay == 0.2
    # Model and voice defaults belong to each provider's builder.
    assert (cfg.stt_model, cfg.stt_language) == (None, None)
    assert cfg.llm_model is None
    assert (cfg.tts_model, cfg.tts_speaker, cfg.tts_codec) == (None, None, None)


def test_keys_are_not_checked_by_config(env):
    # Which key is required depends on the selected providers, so loading
    # never fails for a missing key; the builder that needs it does.
    env.delenv("SARVAM_API_KEY")
    assert load_settings().sarvam_api_key == ""


def test_env_overrides_default(env):
    env.setenv("STT_MODEL", "saaras:v3")
    env.setenv("MIN_ENDPOINTING_DELAY", "0.5")
    cfg = load_settings()
    assert cfg.stt_model == "saaras:v3"
    assert cfg.min_endpointing_delay == 0.5


def test_blank_value_falls_back_to_default(env):
    env.setenv("STT_MODEL", "")
    env.setenv("TTS_SPEAKER", "  ")
    cfg = load_settings()
    assert cfg.stt_model is None
    assert cfg.tts_speaker is None


def test_non_numeric_number_is_a_config_error(env):
    env.setenv("STT_SAMPLE_RATE", "sixteen")
    with pytest.raises(ConfigError, match="STT_SAMPLE_RATE must be a number"):
        load_settings()


def test_settings_are_immutable(env):
    cfg = load_settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.llm_model = "other"
