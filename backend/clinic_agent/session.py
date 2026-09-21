"""Assembles the voice pipeline.

The only module that knows STT, LLM and TTS are combined into one session.
"""

from __future__ import annotations

from livekit.agents import AgentSession

from clinic_agent.config import Settings
from clinic_agent.providers import build_llm, build_stt, build_tts


def build_session(cfg: Settings) -> AgentSession:
    return AgentSession(
        stt=build_stt(cfg),
        llm=build_llm(cfg),
        tts=build_tts(cfg),
        turn_handling={
            # Trust Sarvam's end-of-speech signal. Must stay explicit: omitting
            # it makes LiveKit fall back to its own turn-detector model.
            "turn_detection": "stt",
            "endpointing": {"min_delay": cfg.min_endpointing_delay},
        },
    )
