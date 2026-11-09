import dataclasses

import pytest

from clinic_agent.config import ConfigError, load_settings


def test_defaults(env):
    cfg = load_settings()
    assert cfg.min_endpointing_delay == 0.2
    # Model and voice defaults belong to each provider's builder.
    assert (cfg.sarvam_stt_model, cfg.sarvam_tts_speaker) == (None, None)
    assert (cfg.sarvam_llm_model, cfg.openai_llm_model) == (None, None)
    assert cfg.hindi_llm == "sarvam"  # Sarvam's brain unless HINDI_LLM says openai


def test_keys_are_not_checked_by_config(env):
    # A missing key turns off the Hindi line (lines.py), so loading never
    # fails for one; the builder that needs it does.
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
    env.setenv("SARVAM_TTS_SPEAKER", "  ")
    cfg = load_settings()
    assert cfg.sarvam_stt_model is None
    assert cfg.sarvam_tts_speaker is None


def test_non_numeric_number_is_a_config_error(env):
    env.setenv("STT_SAMPLE_RATE", "sixteen")
    with pytest.raises(ConfigError, match="STT_SAMPLE_RATE must be a number"):
        load_settings()


def test_settings_are_immutable(env):
    cfg = load_settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.openai_llm_model = "other"


def test_old_shared_setting_is_refused_with_its_new_names(env):
    # Silently ignoring it would change the voice or model with no warning.
    env.setenv("TTS_SPEAKER", "suhani")
    with pytest.raises(ConfigError, match="TTS_SPEAKER -> SARVAM_TTS_SPEAKER"):
        load_settings()
    env.setenv("TTS_SPEAKER", "")
    load_settings()  # blank is harmless


@pytest.mark.parametrize("name", ["STT_PROVIDER", "LLM_PROVIDER", "TTS_PROVIDER"])
def test_a_setting_the_language_lines_replaced_is_refused(env, name):
    # The Hindi line picks the vendors now: a leftover would look like it
    # chose them while doing nothing.
    env.setenv(name, "sarvam")
    with pytest.raises(ConfigError, match=f"remove from .env: {name}"):
        load_settings()
    env.setenv(name, "")
    load_settings()  # blank is harmless


def test_retired_settings_are_named_once_per_reason(env):
    for name in ("STT_PROVIDER", "LLM_PROVIDER", "TTS_PROVIDER"):
        env.setenv(name, "x")
    with pytest.raises(ConfigError) as err:
        load_settings()
    assert str(err.value).count("calls run on the Hindi line") == 1
    assert "STT_PROVIDER, LLM_PROVIDER, TTS_PROVIDER" in str(err.value)


def test_a_leftover_line_of_the_removed_vendor_is_refused(env):
    # Harsh (2026-11-08): the English line's vendor is gone. A key left in
    # .env would look like it still did something, so it is named to remove.
    env.setenv("ELEVENLABS_API_KEY", "old-key")
    env.setenv("ELEVENLABS_TTS_VOICE", "voice-123")
    with pytest.raises(ConfigError) as err:
        load_settings()
    assert str(err.value) == ("remove from .env: ELEVENLABS_API_KEY, ELEVENLABS_TTS_VOICE "
                              "(the English line and its vendor were removed on 2026-11-08)")
    env.setenv("ELEVENLABS_API_KEY", "")
    env.setenv("ELEVENLABS_TTS_VOICE", "")
    load_settings()  # blank lines are harmless


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


@pytest.mark.parametrize(("name", "bad"), [
    ("SARVAM_TTS_PACE", "0.4"), ("SARVAM_TTS_PACE", "2.5"),
    ("SARVAM_TTS_PITCH", "-0.6"), ("SARVAM_TTS_PITCH", "0.75"),
])
def test_voice_speed_and_pitch_outside_sarvams_range_stop_startup(env, name, bad):
    env.setenv(name, bad)
    with pytest.raises(ConfigError, match=name):
        load_settings()
