import dataclasses

import pytest

from clinic_agent.config import ConfigError, load_settings


def test_defaults(env):
    cfg = load_settings()
    assert (cfg.stt_provider, cfg.llm_provider, cfg.tts_provider) == ("sarvam",) * 3
    assert cfg.min_endpointing_delay == 0.2
    # Model and voice defaults belong to each provider's builder.
    assert (cfg.sarvam_stt_model, cfg.elevenlabs_stt_model) == (None, None)
    assert (cfg.sarvam_llm_model, cfg.openai_llm_model) == (None, None)
    assert (cfg.sarvam_tts_speaker, cfg.elevenlabs_tts_voice) == (None, None)


def test_keys_are_not_checked_by_config(env):
    # Which key is required depends on the selected providers, so loading
    # never fails for a missing key; the builder that needs it does.
    env.delenv("SARVAM_API_KEY")
    assert load_settings().sarvam_api_key == ""


def test_env_overrides_default(env):
    env.setenv("SARVAM_STT_MODEL", "saaras:v3")
    env.setenv("MIN_ENDPOINTING_DELAY", "0.5")
    cfg = load_settings()
    assert cfg.sarvam_stt_model == "saaras:v3"
    assert cfg.min_endpointing_delay == 0.5


def test_blank_value_falls_back_to_default(env):
    env.setenv("SARVAM_STT_MODEL", "")
    env.setenv("ELEVENLABS_TTS_VOICE", "  ")
    cfg = load_settings()
    assert cfg.sarvam_stt_model is None
    assert cfg.elevenlabs_tts_voice is None


def test_non_numeric_number_is_a_config_error(env):
    env.setenv("STT_SAMPLE_RATE", "sixteen")
    with pytest.raises(ConfigError, match="STT_SAMPLE_RATE must be a number"):
        load_settings()


def test_settings_are_immutable(env):
    cfg = load_settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.openai_llm_model = "other"


def test_each_vendor_keeps_its_own_settings(env):
    # Switching the stack is only the *_PROVIDER lines: both vendors'
    # values sit in .env at once and neither overwrites the other.
    env.setenv("SARVAM_TTS_SPEAKER", "suhani")
    env.setenv("ELEVENLABS_TTS_VOICE", "voice-123")
    cfg = load_settings()
    assert (cfg.sarvam_tts_speaker, cfg.elevenlabs_tts_voice) == ("suhani", "voice-123")


def test_old_shared_setting_is_refused_with_its_new_names(env):
    # Silently ignoring it would change the voice or model with no warning.
    env.setenv("TTS_SPEAKER", "suhani")
    with pytest.raises(ConfigError, match="TTS_SPEAKER -> SARVAM_TTS_SPEAKER / ELEVENLABS_TTS_VOICE"):
        load_settings()
    env.setenv("TTS_SPEAKER", "")
    load_settings()  # blank is harmless


def test_dashboard_login_defaults_to_google_and_rejects_typos(env):
    assert load_settings().dashboard_login == "google"
    env.setenv("DASHBOARD_LOGIN", "Off")
    assert load_settings().dashboard_login == "off"
    env.setenv("DASHBOARD_LOGIN", "none")
    with pytest.raises(ConfigError, match="DASHBOARD_LOGIN must be one of google, off"):
        load_settings()


def test_admin_emails_are_a_lowercased_set(env):
    env.setenv("ADMIN_EMAILS", " Harsh@Example.com, ,owner@clinic.in ")
    assert load_settings().admin_emails == {"harsh@example.com", "owner@clinic.in"}
