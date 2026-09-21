"""Language-model builders.

Every builder returns a `livekit.agents.llm.LLM`.
"""

from __future__ import annotations

from collections.abc import Callable

from livekit.agents import llm
from livekit.plugins import openai, sarvam

from clinic_agent.config import Settings, require_key


def _sarvam(cfg: Settings) -> llm.LLM:
    return sarvam.LLM(
        model=cfg.llm_model or "sarvam-105b-conversations",
        api_key=require_key(cfg.sarvam_api_key, "SARVAM_API_KEY"),
    )


def _openai(cfg: Settings) -> llm.LLM:
    # gpt-4.1-mini: no reasoning step, so the first token arrives fast enough
    # for a phone call; the gpt-5 family thinks before answering.
    return openai.LLM(
        model=cfg.llm_model or "gpt-4.1-mini",
        api_key=require_key(cfg.openai_api_key, "OPENAI_API_KEY"),
    )


BUILDERS: dict[str, Callable[[Settings], llm.LLM]] = {
    "sarvam": _sarvam,
    "openai": _openai,
}


def build_llm(cfg: Settings) -> llm.LLM:
    try:
        builder = BUILDERS[cfg.llm_provider]
    except KeyError:
        raise ValueError(
            f"unknown LLM provider {cfg.llm_provider!r}; "
            f"available: {sorted(BUILDERS)}"
        ) from None
    return builder(cfg)
