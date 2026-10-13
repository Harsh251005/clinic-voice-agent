"""Language-model builders.

Every builder returns a `livekit.agents.llm.LLM`.
"""

from __future__ import annotations

import re
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
    # gpt-4.1-mini (the default: fastest capable model measured 2026-10-12,
    # ~1.0 s first token vs gpt-6-luna's 1.6 s) does not reason. Reasoning
    # models (gpt-5 and later, o*) get reasoning_effort "none" explicitly: Chat Completions refuses
    # tools with reasoning on (400 on every turn, checked with gpt-6-luna),
    # the plugin only sets it for model names it already knows, and no
    # reasoning step keeps the first token fast enough for a phone call.
    model = cfg.openai_llm_model or "gpt-4.1-mini"
    options = {"reasoning_effort": "none"} if _reasons(model) else {}
    return openai.LLM(
        model=model,
        api_key=require_key(cfg.openai_api_key, "OPENAI_API_KEY"),
        **options,
    )


def _reasons(model: str) -> bool:
    """gpt-5 and every later generation, and the o-series."""
    return bool(re.match(r"(gpt-([5-9]|\d{2,})|o\d)", model))


# Allowed vendors are Sarvam (the Hindi line) and OpenAI (the English line). Don't add others.
BUILDERS: dict[str, Callable[[Settings], llm.LLM]] = {
    "sarvam": _sarvam,
    "openai": _openai,
}


def build_llm(cfg: Settings, vendor: str) -> llm.LLM:
    """`vendor`'s LLM, as a call's language line names it (clinic_agent/lines.py)."""
    try:
        builder = BUILDERS[vendor]
    except KeyError:
        raise ValueError(f"unknown LLM vendor {vendor!r}; available: {sorted(BUILDERS)}") from None
    return builder(cfg)
