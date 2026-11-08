import pytest

from clinic_agent.config import load_settings
from clinic_agent.lines import Line, line_for
from clinic_agent.session import build_session

HINDI = Line("hi", stt="sarvam", llm="sarvam", tts="sarvam")  # the env fixture sets only a Sarvam key


async def test_turn_detection_trusts_stt(env):
    env.setenv("MIN_ENDPOINTING_DELAY", "0.3")
    session = build_session(load_settings(), HINDI)
    opts = session.options
    assert opts.turn_handling["turn_detection"] == "stt"
    assert opts.turn_handling["endpointing"]["min_delay"] == 0.3


async def test_interruptions_use_the_local_vad_in_every_mode(env):
    # Explicit mode "vad": otherwise console/dev would use LiveKit's adaptive
    # model and start wouldn't, so local tests wouldn't match production.
    env.setenv("INTERRUPT_MIN_SPEECH", "0.25")
    session = build_session(load_settings(), HINDI)
    assert session.vad is not None
    assert session.interruption_detection == "vad"
    assert session.options.interruption["min_duration"] == 0.25


async def test_vad_waits_out_a_comma_pause(env):
    # At LiveKit's 0.25 s a comma pause ended the utterance, and a batch STT
    # transcribed only "नमस्ते" of "नमस्ते, आपका अपॉइंटमेंट ...".
    env.setenv("VAD_MIN_SILENCE", "0.7")
    assert build_session(load_settings(), HINDI).vad._opts.min_silence_duration == 0.7


@pytest.mark.parametrize(("brain", "vendors"), [
    ("sarvam", ["sarvam", "sarvam", "sarvam"]),
    ("openai", ["sarvam", "openai", "sarvam"]),
])
async def test_the_hindi_line_is_sarvam_with_the_brain_hindi_llm_names(env, brain, vendors):
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("HINDI_LLM", brain)
    cfg = load_settings()
    session = build_session(cfg, line_for(cfg, "hi"))
    # livekit.plugins.<vendor>...: which vendor's plugin built each part
    built = [type(p).__module__.split(".")[2] for p in (session.stt, session.llm, session.tts)]
    assert built == vendors


async def test_text_only_session_builds_no_speech_providers(env):
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.delenv("SARVAM_API_KEY")  # not needed: no STT or TTS is built
    env.setenv("HINDI_LLM", "openai")
    cfg = load_settings()
    session = build_session(cfg, line_for(cfg, "hi"), text_only=True)
    assert session.stt is None and session.tts is None and session.vad is None
    assert session.options.turn_handling["turn_detection"] == "manual"
