import pytest
from livekit.agents import llm, stt, tts
from livekit.plugins import elevenlabs

from clinic_agent.config import ConfigError, load_settings
from clinic_agent.providers import build_llm, build_stt, build_tts


def test_sarvam_builders_return_livekit_base_classes(env):
    cfg = load_settings()
    assert isinstance(build_stt(cfg, "sarvam"), stt.STT)
    assert isinstance(build_llm(cfg, "sarvam"), llm.LLM)
    assert isinstance(build_tts(cfg, "sarvam"), tts.TTS)


def test_stt_is_streaming(env):
    # Streaming is why Sarvam can do its own end-of-turn detection.
    assert build_stt(load_settings(), "sarvam").capabilities.streaming


def test_sarvam_defaults(env):
    cfg = load_settings()
    s = build_stt(cfg, "sarvam")
    assert (s.model, s._opts.language) == ("saaras:v3", "unknown")
    assert build_llm(cfg, "sarvam").model == "sarvam-105b-conversations"
    t = build_tts(cfg, "sarvam")
    assert (t.model, t._opts.speaker, t._opts.output_audio_codec) == ("bulbul:v3", "suhani", "linear16")
    assert t._opts.target_language_code == "hi-IN"  # the Hindi line: Devanagari replies
    assert t.sample_rate == 24000


def test_sarvam_voice_gets_whole_sentences(env):
    # Sarvam voices each piece it gets as one take; pieces cut mid-sentence
    # made the tone change halfway through. Ours cut at "।", and Sarvam must
    # not re-cut them.
    import inspect

    from livekit.plugins.sarvam import tts as sarvam_tts

    from clinic_agent.providers.sentences import MAX_PIECE, SentenceTokenizer

    t = build_tts(load_settings(), "sarvam")
    assert isinstance(t._opts.word_tokenizer, SentenceTokenizer)
    assert t._opts.max_chunk_length >= MAX_PIECE
    # The plugin has no argument for its splitter; this fails if an upgrade
    # stops reading the option we set, instead of silently reverting.
    assert "self._opts.word_tokenizer" in inspect.getsource(sarvam_tts.SynthesizeStream._run)


def test_openai_llm(env):
    env.setenv("OPENAI_API_KEY", "sk-test")
    m = build_llm(load_settings(), "openai")
    assert isinstance(m, llm.LLM)
    assert m.model == "gpt-6-luna"
    assert m._opts.reasoning_effort == "none"  # a reasoning model: tools need it off


def test_openai_model_override(env):
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
    assert build_llm(load_settings(), "openai").model == "gpt-4o-mini"


@pytest.mark.parametrize(
    ("model", "effort"),
    [("gpt-6-luna", "none"), ("gpt-5.6-luna", "none"), ("gpt-5-mini", "none"), ("gpt-10", "none"),
     ("o4-mini", "none"), ("gpt-4.1-mini", None), ("gpt-4o-mini", None)],
)
def test_openai_reasoning_is_off_so_tools_work(env, model, effort):
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("OPENAI_LLM_MODEL", model)
    opts = build_llm(load_settings(), "openai")._opts
    got = opts.reasoning_effort if isinstance(opts.reasoning_effort, str) else None
    assert got == effort


def test_elevenlabs_tts(env):
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    t = build_tts(load_settings(), "elevenlabs")
    assert isinstance(t, tts.TTS)
    assert t.model == "eleven_v3_conversational"
    assert t._opts.voice_id == elevenlabs.DEFAULT_VOICE_ID
    assert t._opts.encoding == "pcm_24000"
    assert t.sample_rate == 24000


def test_elevenlabs_stt(env):
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    s = build_stt(load_settings(), "elevenlabs")
    assert isinstance(s, stt.STT)
    # Batch: LiveKit cuts utterances with the session's VAD and sends each one.
    assert s.model == "scribe_v2"
    assert not s.capabilities.streaming
    assert s._opts.language_code == "en"  # the English line; auto-detect breaks on live calls


def test_elevenlabs_realtime_stt_commits_on_silence(env):
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    env.setenv("ELEVENLABS_STT_MODEL", "scribe_v2_realtime")
    s = build_stt(load_settings(), "elevenlabs")
    assert s.capabilities.streaming
    # Manual commits would wait for a flush a live call never sends.
    assert s._opts.server_vad == {}  # given, so commit_strategy=vad


def test_each_vendor_reads_its_own_voice_setting(env):
    env.setenv("ELEVENLABS_API_KEY", "el-test")
    env.setenv("SARVAM_TTS_SPEAKER", "shubh")
    env.setenv("ELEVENLABS_TTS_VOICE", "voice-123")
    cfg = load_settings()
    assert build_tts(cfg, "sarvam")._opts.speaker == "shubh"
    assert build_tts(cfg, "elevenlabs")._opts.voice_id == "voice-123"


def test_only_the_allowed_vendors_are_registered():
    # Harsh's rule: speech is Sarvam or ElevenLabs, the LLM Sarvam or OpenAI.
    from clinic_agent.providers import llm as llm_mod, stt as stt_mod, tts as tts_mod

    assert set(stt_mod.BUILDERS) == {"sarvam", "elevenlabs"}
    assert set(tts_mod.BUILDERS) == {"sarvam", "elevenlabs"}
    assert set(llm_mod.BUILDERS) == {"sarvam", "openai"}


@pytest.mark.parametrize(
    ("vendor", "key", "build"),
    [
        ("sarvam", "SARVAM_API_KEY", build_llm),
        ("sarvam", "SARVAM_API_KEY", build_stt),
        ("sarvam", "SARVAM_API_KEY", build_tts),
        ("openai", "OPENAI_API_KEY", build_llm),
        ("elevenlabs", "ELEVENLABS_API_KEY", build_tts),
        ("elevenlabs", "ELEVENLABS_API_KEY", build_stt),
    ],
)
def test_each_vendor_requires_its_own_key(env, vendor, key, build):
    env.delenv("SARVAM_API_KEY")
    with pytest.raises(ConfigError, match=f"{key} is not set"):
        build(load_settings(), vendor)


@pytest.mark.parametrize(
    ("build", "available"),
    [(build_stt, "['elevenlabs', 'sarvam']"), (build_llm, "['openai', 'sarvam']"), (build_tts, "['elevenlabs', 'sarvam']")],
)
def test_unknown_vendor_lists_available(env, build, available):
    with pytest.raises(ValueError, match=rf"unknown .* vendor 'nope'; available: {__import__('re').escape(available)}"):
        build(load_settings(), "nope")
