"""Language-model builders.

Every builder returns a `livekit.agents.llm.LLM`.
"""

from __future__ import annotations

from collections.abc import Callable

from livekit.agents import llm
from livekit.plugins import sarvam

from clinic_agent.config import Settings


def _sarvam(cfg: Settings) -> llm.LLM:
    return sarvam.LLM(
        model=cfg.llm_model,
        api_key=cfg.sarvam_api_key,
    )


BUILDERS: dict[str, Callable[[Settings], llm.LLM]] = {
    "sarvam": _sarvam,
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
