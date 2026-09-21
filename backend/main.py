"""Clinic voice agent.

    uv run python main.py console   talk to it locally (no LiveKit minutes)
    uv run python main.py dev       join a LiveKit room, reload on save
    uv run python main.py start     production worker
"""

from __future__ import annotations

import asyncio
import logging
import sys

from livekit.agents import JobContext, WorkerOptions, cli

from clinic_agent.agent import ClinicAgent
from clinic_agent.config import ConfigError, load_settings
from clinic_agent.context import clinic_now, load_clinic
from clinic_agent.prompts import build_instructions
from clinic_agent.providers import build_llm, build_stt, build_tts
from clinic_agent.session import build_session
from clinic_agent.store.repo import NotFound

logger = logging.getLogger("clinic-agent")


async def entrypoint(ctx: JobContext) -> None:
    cfg = load_settings()
    logger.info(
        "starting session: stt=%s/%s llm=%s/%s tts=%s/%s speaker=%s",
        cfg.stt_provider, cfg.stt_model,
        cfg.llm_provider, cfg.llm_model,
        cfg.tts_provider, cfg.tts_model, cfg.tts_speaker,
    )

    clinic, time_off = await asyncio.to_thread(load_clinic, cfg)
    logger.info("clinic %s: %s", clinic.id, clinic.name)
    instructions = build_instructions(clinic, time_off, clinic_now(clinic.timezone))

    session = build_session(cfg)
    await session.start(agent=ClinicAgent(instructions), room=ctx.room)


if __name__ == "__main__":
    # Fail before the worker starts rather than on the first call, and report
    # it as a one-line setup error instead of a traceback. Building the
    # providers here is what catches an unknown *_PROVIDER name; the session
    # itself needs a running event loop, so it is left to the entrypoint.
    # Loading the clinic here catches a CLINIC_ID missing from the database.
    try:
        cfg = load_settings()
        build_stt(cfg), build_llm(cfg), build_tts(cfg)
        load_clinic(cfg)
    except NotFound:
        sys.exit(
            f"configuration error: clinic {cfg.clinic_id} is not in {cfg.database_url}. "
            "Create it in the dashboard or run: uv run python -m seeds.demo_clinic"
        )
    except (ConfigError, ValueError) as err:
        sys.exit(f"configuration error: {err}")

    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
