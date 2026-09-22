"""Clinic voice agent.

    uv run python main.py console   talk to it locally (no LiveKit minutes)
    uv run python main.py console --text
                                    type to it: LLM only, no STT/TTS cost
    uv run python main.py dev       join LiveKit rooms it is dispatched to, reload on save
    uv run python main.py start     production worker

One worker answers for every clinic: each call's dispatch names its clinic
(see clinic_agent/dispatch.py). Console has no dispatch, so it takes
`--clinic <id>`, or uses the only clinic in the database.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from livekit.agents import JobContext, WorkerOptions, cli

from clinic_agent.agent import ClinicAgent
from clinic_agent.call_limit import end_after
from clinic_agent.config import ConfigError, load_settings
from clinic_agent.context import clinic_now, load_clinic, local_clinic
from clinic_agent.dispatch import AGENT_NAME, NoClinic, clinic_id_from
from clinic_agent.prompts import build_instructions
from clinic_agent.providers import build_llm, build_stt, build_tts
from clinic_agent.session import build_session
from clinic_agent.store.db import sessions_for
from clinic_agent.store.migrations import SchemaOutdated
from clinic_agent.store.repo import NotFound
from clinic_agent.tools.booking import ClinicLink, booking_tools
from clinic_agent.tools.call import end_call_tool

logger = logging.getLogger("clinic-agent")

CONSOLE = sys.argv[1:2] == ["console"]
# `console --text` is the cheap testing mode: no speech providers are built.
# Console jobs run in this same process, so the entrypoint can read it.
TEXT_ONLY = CONSOLE and "--text" in sys.argv
# The clinic a console call is for, set at boot. Always None under dev and
# start: those calls run in child processes and must name their clinic.
LOCAL_CLINIC: int | None = None


def _take_clinic_flag(argv: list[str]) -> int | None:
    """Remove `--clinic N` from argv (LiveKit's CLI rejects unknown flags)."""
    for i, arg in enumerate(argv):
        if arg == "--clinic" or arg.startswith("--clinic="):
            value = arg.partition("=")[2] or (argv[i + 1] if i + 1 < len(argv) else "")
            del argv[i : i + (1 if "=" in arg else 2)]
            if not value.isdigit():
                raise ValueError(f"--clinic needs a clinic id, got {value!r}")
            if not CONSOLE:
                raise ValueError("--clinic is for console only; dev and start calls name their clinic")
            return int(value)
    return None


async def entrypoint(ctx: JobContext) -> None:
    cfg = load_settings()
    if TEXT_ONLY:
        logger.info("starting text-only session: llm=%s/%s", cfg.llm_provider, cfg.llm_model or "default")
    else:
        logger.info(
            "starting session: stt=%s/%s llm=%s/%s tts=%s/%s speaker=%s",
            cfg.stt_provider, cfg.stt_model or "default",
            cfg.llm_provider, cfg.llm_model or "default",
            cfg.tts_provider, cfg.tts_model or "default", cfg.tts_speaker or "default",
        )

    try:
        clinic_id = clinic_id_from(ctx.job.metadata, fallback=LOCAL_CLINIC)
        clinic, time_off = await asyncio.to_thread(load_clinic, cfg, clinic_id)
    except (NoClinic, NotFound) as err:
        # Never answer as a guessed clinic: wrong name, wrong doctors, wrong bookings.
        logger.error("refusing call in room %s: %s", ctx.room.name, err)
        ctx.shutdown(reason=f"no clinic: {err}")
        return
    logger.info("clinic %s: %s", clinic.id, clinic.name)
    instructions = build_instructions(clinic, time_off, clinic_now(clinic.timezone))
    link = ClinicLink(clinic.id, clinic.timezone, sessions_for(cfg.database_url))
    tools = [*booking_tools(link), end_call_tool()]

    session = build_session(cfg, text_only=TEXT_ONLY)
    await session.start(agent=ClinicAgent(instructions, tools), room=ctx.room)

    limit = asyncio.create_task(end_after(session, ctx, cfg.max_call_minutes * 60))

    async def _stop_limit() -> None:
        limit.cancel()

    ctx.add_shutdown_callback(_stop_limit)


if __name__ == "__main__":
    # Fail before the worker starts rather than on the first call, and report
    # it as a one-line setup error instead of a traceback. Building the
    # providers here is what catches an unknown *_PROVIDER name; the session
    # itself needs a running event loop, so it is left to the entrypoint.
    # Opening the database here catches an old schema; console also resolves
    # its clinic, since it has no dispatch to name one.
    try:
        requested = _take_clinic_flag(sys.argv)
        cfg = load_settings()
        build_llm(cfg)
        if not TEXT_ONLY:
            build_stt(cfg), build_tts(cfg)
        sessions_for(cfg.database_url)
        if CONSOLE:
            LOCAL_CLINIC = local_clinic(cfg, requested)
    except NotFound as err:
        sys.exit(f"configuration error: {err}")
    except (ConfigError, SchemaOutdated, ValueError) as err:
        sys.exit(f"configuration error: {err}")

    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name=AGENT_NAME))
