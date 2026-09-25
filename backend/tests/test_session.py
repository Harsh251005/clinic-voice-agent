from clinic_agent.config import load_settings
from clinic_agent.session import build_session


async def test_turn_detection_trusts_stt(env):
    env.setenv("MIN_ENDPOINTING_DELAY", "0.3")
    session = build_session(load_settings())
    opts = session.options
    assert opts.turn_handling["turn_detection"] == "stt"
    assert opts.turn_handling["endpointing"]["min_delay"] == 0.3


async def test_interruptions_use_the_local_vad_in_every_mode(env):
    # Explicit mode "vad": otherwise console/dev would use LiveKit's adaptive
    # model and start wouldn't, so local tests wouldn't match production.
    env.setenv("INTERRUPT_MIN_SPEECH", "0.25")
    session = build_session(load_settings())
    assert session.vad is not None
    assert session.interruption_detection == "vad"
    assert session.options.interruption["min_duration"] == 0.25


async def test_vad_waits_out_a_comma_pause(env):
    # At LiveKit's 0.25 s a comma pause ended the utterance, and a batch STT
    # transcribed only "नमस्ते" of "नमस्ते, आपका अपॉइंटमेंट ...".
    env.setenv("VAD_MIN_SILENCE", "0.7")
    assert build_session(load_settings()).vad._opts.min_silence_duration == 0.7


async def test_text_only_session_builds_no_speech_providers(env):
    env.setenv("LLM_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.delenv("SARVAM_API_KEY")  # not needed: no STT or TTS is built
    session = build_session(load_settings(), text_only=True)
    assert session.stt is None and session.tts is None and session.vad is None
    assert session.options.turn_handling["turn_detection"] == "manual"
