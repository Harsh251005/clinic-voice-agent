import pytest
from livekit.agents import llm, stt, tts
from livekit.plugins import elevenlabs

from clinic_agent.config import ConfigError, load_settings
from clinic_agent.providers import build_llm, build_stt, build_tts


def test_sarvam_builders_return_livekit_base_classes(env):
    cfg = load_settings()
    assert isinstance(build_stt(cfg), stt.STT)
    assert isinstance(build_llm(cfg), llm.LLM)
    assert isinstance(build_tts(cfg), tts.TTS)


def test_stt_is_streaming(env):
    # Streaming is why Sarvam can do its own end-of-turn detection.
    assert build_stt(load_settings()).capabilities.streaming


def test_sarvam_defaults(env):
    cfg = load_settings()
    assert build_llm(cfg).model == "sarvam-105b-conversations"
    t = build_tts(cfg)
    assert (t.model, t._opts.speaker, t._opts.output_audio_codec) == ("bulbul:v3", "suhani", "linear16")
    assert t.sample_rate == 24000


def test_openai_llm(env):
    env.setenv("LLM_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test")
    m = build_llm(load_settings())
    assert isinstance(m, llm.LLM)
    assert m.model == "gpt-4.1-mini"


def test_openai_model_override(env):
    env.setenv("LLM_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("LLM_MODEL", "gpt-4o-mini")
    assert build_llm(load_settings()).model == "gpt-4o-mini"


def test_elevenlabs_tts(env):
    env.setenv("TTS_PROVIDER", "elevenlabs")
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    t = build_tts(load_settings())
    assert isinstance(t, tts.TTS)
    assert t.model == "eleven_v3_conversational"
    assert t._opts.voice_id == elevenlabs.DEFAULT_VOICE_ID
    assert t._opts.encoding == "pcm_24000"
    assert t.sample_rate == 24000


@pytest.mark.parametrize(
    ("provider_var", "provider", "key", "build"),
    [
        ("LLM_PROVIDER", "sarvam", "SARVAM_API_KEY", build_llm),
        ("STT_PROVIDER", "sarvam", "SARVAM_API_KEY", build_stt),
        ("TTS_PROVIDER", "sarvam", "SARVAM_API_KEY", build_tts),
        ("LLM_PROVIDER", "openai", "OPENAI_API_KEY", build_llm),
        ("TTS_PROVIDER", "elevenlabs", "ELEVENLABS_API_KEY", build_tts),
    ],
)
def test_selected_provider_requires_its_key(env, provider_var, provider, key, build):
    env.delenv("SARVAM_API_KEY")
    env.setenv(provider_var, provider)
    with pytest.raises(ConfigError, match=f"{key} is not set"):
        build(load_settings())


def test_unselected_vendor_needs_no_key(env):
    # OpenAI + ElevenLabs selected: no Sarvam key needed for them.
    env.delenv("SARVAM_API_KEY")
    env.setenv("LLM_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("TTS_PROVIDER", "elevenlabs")
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    cfg = load_settings()
    build_llm(cfg)
    build_tts(cfg)


@pytest.mark.parametrize(
    ("var", "build", "available"),
    [
        ("STT_PROVIDER", build_stt, "['sarvam']"),
        ("LLM_PROVIDER", build_llm, "['openai', 'sarvam']"),
        ("TTS_PROVIDER", build_tts, "['elevenlabs', 'sarvam']"),
    ],
)
def test_unknown_provider_lists_available(env, var, build, available):
    env.setenv(var, "nope")
    with pytest.raises(ValueError, match=rf"unknown .* provider 'nope'; available: {__import__('re').escape(available)}"):
        build(load_settings())
