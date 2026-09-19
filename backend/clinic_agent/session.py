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
        # Trust Sarvam's end-of-speech signal instead of running a local VAD.
        turn_detection="stt",
        min_endpointing_delay=cfg.min_endpointing_delay,
    )
