import pytest
from livekit.agents import llm, stt, tts

from clinic_agent.config import load_settings
from clinic_agent.providers import build_llm, build_stt, build_tts


def test_builders_return_livekit_base_classes(env):
    cfg = load_settings()
    assert isinstance(build_stt(cfg), stt.STT)
    assert isinstance(build_llm(cfg), llm.LLM)
    assert isinstance(build_tts(cfg), tts.TTS)


def test_stt_is_streaming(env):
    # Streaming is why no local VAD is needed.
    assert build_stt(load_settings()).capabilities.streaming


def test_tts_gets_configured_voice_and_codec(env):
    t = build_tts(load_settings())
    assert t.sample_rate == 24000
    assert t._opts.speaker == "suhani"
    assert t._opts.output_audio_codec == "linear16"


@pytest.mark.parametrize(
    ("var", "build"),
    [("STT_PROVIDER", build_stt), ("LLM_PROVIDER", build_llm), ("TTS_PROVIDER", build_tts)],
)
def test_unknown_provider_lists_available(env, var, build):
    env.setenv(var, "eleven")
    with pytest.raises(ValueError, match=r"unknown .* provider 'eleven'; available: \['sarvam'\]"):
        build(load_settings())
