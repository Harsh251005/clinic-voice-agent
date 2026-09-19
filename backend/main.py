"""Clinic voice agent.

    uv run python main.py console   talk to it locally (no LiveKit minutes)
    uv run python main.py dev       join a LiveKit room, reload on save
    uv run python main.py start     production worker
"""

from __future__ import annotations

import logging
import sys

from livekit.agents import JobContext, WorkerOptions, cli

from clinic_agent.agent import ClinicAgent
from clinic_agent.config import ConfigError, load_settings
from clinic_agent.session import build_session

logger = logging.getLogger("clinic-agent")


async def entrypoint(ctx: JobContext) -> None:
    cfg = load_settings()
    logger.info(
        "starting session: stt=%s/%s llm=%s/%s tts=%s/%s speaker=%s",
        cfg.stt_provider, cfg.stt_model,
        cfg.llm_provider, cfg.llm_model,
        cfg.tts_provider, cfg.tts_model, cfg.tts_speaker,
    )

    session = build_session(cfg)
    await session.start(agent=ClinicAgent(), room=ctx.room)


if __name__ == "__main__":
    # Fail before the worker starts rather than on the first call, and report
    # it as a one-line setup error instead of a traceback.
    try:
        load_settings()
    except ConfigError as err:
        sys.exit(f"configuration error: {err}")

    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
