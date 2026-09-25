"""Assembles the voice pipeline.

The only module that knows STT, LLM and TTS are combined into one session.
"""

from __future__ import annotations

from livekit.agents import AgentSession, inference

from clinic_agent.config import Settings
from clinic_agent.providers import build_llm, build_stt, build_tts


def build_session(cfg: Settings, text_only: bool = False) -> AgentSession:
    """The voice pipeline, or with text_only just the LLM: typed in, printed out.

    Text-only builds no STT or TTS at all, so testing the conversation, tools
    and database spends only LLM tokens and needs no speech-provider keys.
    """
    if text_only:
        # Typed messages are whole turns already: nothing to detect, no VAD.
        return AgentSession(llm=build_llm(cfg), vad=None, turn_handling={"turn_detection": "manual"})
    return AgentSession(
        stt=build_stt(cfg),
        llm=build_llm(cfg),
        tts=build_tts(cfg),
        # Local Silero VAD, only for barge-in: the STT still ends turns.
        vad=inference.VAD(model="silero"),
        turn_handling={
            # Trust Sarvam's end-of-speech signal. Must stay explicit: omitting
            # it makes LiveKit fall back to its own turn-detector model.
            "turn_detection": "stt",
            "endpointing": {"min_delay": cfg.min_endpointing_delay},
            # Plain VAD interruption in every mode. Left unset, console/dev
            # use LiveKit Cloud's adaptive model and start doesn't, so what
            # you hear locally wouldn't match a real call.
            "interruption": {"mode": "vad", "min_duration": cfg.interrupt_min_speech},
        },
    )
