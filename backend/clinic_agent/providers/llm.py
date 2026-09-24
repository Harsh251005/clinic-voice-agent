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
        model=cfg.sarvam_llm_model or "sarvam-105b-conversations",
        api_key=require_key(cfg.sarvam_api_key, "SARVAM_API_KEY"),
    )


def _openai(cfg: Settings) -> llm.LLM:
    # gpt-4.1-mini: no reasoning step, so the first token arrives fast enough
    # for a phone call. Reasoning models (gpt-5*, o*) get reasoning_effort
    # "none" explicitly: Chat Completions refuses tools with reasoning on,
    # and the plugin only sets it for model names it already knows, so a
    # newer model (e.g. gpt-5.6-luna) would fail on every turn.
    model = cfg.openai_llm_model or "gpt-4.1-mini"
    options = {"reasoning_effort": "none"} if _reasons(model) else {}
    return openai.LLM(
        model=model,
        api_key=require_key(cfg.openai_api_key, "OPENAI_API_KEY"),
        **options,
    )


def _reasons(model: str) -> bool:
    return model.startswith(("gpt-5", "o1", "o3", "o4"))


# Allowed vendors are Sarvam (production) and OpenAI. Don't add others.
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
