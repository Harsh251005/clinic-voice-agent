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
    s = build_stt(cfg)
    assert (s.model, s._opts.language) == ("saaras:v3", "unknown")
    assert build_llm(cfg).model == "sarvam-105b-conversations"
    t = build_tts(cfg)
    assert (t.model, t._opts.speaker, t._opts.output_audio_codec) == ("bulbul:v3", "suhani", "linear16")
    assert t.sample_rate == 24000


def test_sarvam_voice_gets_whole_sentences(env):
    # Sarvam voices each piece it gets as one take; pieces cut mid-sentence
    # made the tone change halfway through. Ours cut at "।", and Sarvam must
    # not re-cut them.
    import inspect

    from livekit.plugins.sarvam import tts as sarvam_tts

    from clinic_agent.providers.sentences import MAX_PIECE, SentenceTokenizer

    t = build_tts(load_settings())
    assert isinstance(t._opts.word_tokenizer, SentenceTokenizer)
    assert t._opts.max_chunk_length >= MAX_PIECE
    # The plugin has no argument for its splitter; this fails if an upgrade
    # stops reading the option we set, instead of silently reverting.
    assert "self._opts.word_tokenizer" in inspect.getsource(sarvam_tts.SynthesizeStream._run)


def test_openai_llm(env):
    env.setenv("LLM_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test")
    m = build_llm(load_settings())
    assert isinstance(m, llm.LLM)
    assert m.model == "gpt-4.1-mini"


def test_openai_model_override(env):
    env.setenv("LLM_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
    assert build_llm(load_settings()).model == "gpt-4o-mini"


@pytest.mark.parametrize(
    ("model", "effort"),
    [("gpt-5.6-luna", "none"), ("gpt-5-mini", "none"), ("o4-mini", "none"), ("gpt-4.1-mini", None)],
)
def test_openai_reasoning_is_off_so_tools_work(env, model, effort):
    env.setenv("LLM_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("OPENAI_LLM_MODEL", model)
    opts = build_llm(load_settings())._opts
    got = opts.reasoning_effort if isinstance(opts.reasoning_effort, str) else None
    assert got == effort


def test_elevenlabs_tts(env):
    env.setenv("TTS_PROVIDER", "elevenlabs")
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    t = build_tts(load_settings())
    assert isinstance(t, tts.TTS)
    assert t.model == "eleven_v3_conversational"
    assert t._opts.voice_id == elevenlabs.DEFAULT_VOICE_ID
    assert t._opts.encoding == "pcm_24000"
    assert t.sample_rate == 24000


def test_elevenlabs_stt(env):
    env.setenv("STT_PROVIDER", "elevenlabs")
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    s = build_stt(load_settings())
    assert isinstance(s, stt.STT)
    # Streaming, so turn detection can trust its end of speech as with Sarvam.
    assert s.model == "scribe_v2_realtime"
    assert s.capabilities.streaming
    assert s._opts.language_code == "hi"  # auto-detect breaks on live calls
    # Commits on silence. Manual commits would wait for a flush a live call never sends.
    assert s._opts.server_vad == {}  # given, so commit_strategy=vad


@pytest.mark.parametrize(("value", "expected"), [("unknown", "hi"), ("", "hi"), ("en", "en")])
def test_elevenlabs_stt_language(env, value, expected):
    # "unknown" (Sarvam's word for auto-detect) becomes Hindi here, so
    # ElevenLabs never turns auto-detect on.
    env.setenv("STT_PROVIDER", "elevenlabs")
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    env.setenv("ELEVENLABS_STT_LANGUAGE", value)
    assert build_stt(load_settings())._opts.language_code == expected


def test_switching_provider_picks_up_that_vendors_own_settings(env):
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    env.setenv("SARVAM_TTS_SPEAKER", "shubh")
    env.setenv("ELEVENLABS_TTS_VOICE", "voice-123")
    assert build_tts(load_settings())._opts.speaker == "shubh"
    env.setenv("TTS_PROVIDER", "elevenlabs")
    assert build_tts(load_settings())._opts.voice_id == "voice-123"


def test_only_the_allowed_vendors_are_registered():
    # Harsh's rule: speech is Sarvam or ElevenLabs, the LLM Sarvam or OpenAI.
    from clinic_agent.providers import llm as llm_mod, stt as stt_mod, tts as tts_mod

    assert set(stt_mod.BUILDERS) == {"sarvam", "elevenlabs"}
    assert set(tts_mod.BUILDERS) == {"sarvam", "elevenlabs"}
    assert set(llm_mod.BUILDERS) == {"sarvam", "openai"}


@pytest.mark.parametrize(
    ("provider_var", "provider", "key", "build"),
    [
        ("LLM_PROVIDER", "sarvam", "SARVAM_API_KEY", build_llm),
        ("STT_PROVIDER", "sarvam", "SARVAM_API_KEY", build_stt),
        ("TTS_PROVIDER", "sarvam", "SARVAM_API_KEY", build_tts),
        ("LLM_PROVIDER", "openai", "OPENAI_API_KEY", build_llm),
        ("TTS_PROVIDER", "elevenlabs", "ELEVENLABS_API_KEY", build_tts),
        ("STT_PROVIDER", "elevenlabs", "ELEVENLABS_API_KEY", build_stt),
    ],
)
def test_selected_provider_requires_its_key(env, provider_var, provider, key, build):
    env.delenv("SARVAM_API_KEY")
    env.setenv(provider_var, provider)
    with pytest.raises(ConfigError, match=f"{key} is not set"):
        build(load_settings())


def test_unselected_vendor_needs_no_key(env):
    # The OpenAI + ElevenLabs testing stack runs with no Sarvam key at all.
    env.delenv("SARVAM_API_KEY")
    env.setenv("STT_PROVIDER", "elevenlabs")
    env.setenv("LLM_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("TTS_PROVIDER", "elevenlabs")
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    cfg = load_settings()
    build_stt(cfg)
    build_llm(cfg)
    build_tts(cfg)


@pytest.mark.parametrize(
    ("var", "build", "available"),
    [
        ("STT_PROVIDER", build_stt, "['elevenlabs', 'sarvam']"),
        ("LLM_PROVIDER", build_llm, "['openai', 'sarvam']"),
        ("TTS_PROVIDER", build_tts, "['elevenlabs', 'sarvam']"),
    ],
)
def test_unknown_provider_lists_available(env, var, build, available):
    env.setenv(var, "nope")
    with pytest.raises(ValueError, match=rf"unknown .* provider 'nope'; available: {__import__('re').escape(available)}"):
        build(load_settings())
