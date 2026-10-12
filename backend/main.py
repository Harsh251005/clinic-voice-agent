"""Clinic voice agent.

    uv run python main.py console   talk to it locally (no LiveKit minutes)
    uv run python main.py console --text
                                    type to it: LLM only, no STT/TTS cost
    uv run python main.py console --language en
                                    the caller's language: hi (default) or en
    uv run python main.py dev       join LiveKit rooms it is dispatched to (restart it after a code change)
    uv run python main.py start     production worker

One worker answers for every clinic: each call's dispatch names its clinic
and language (see clinic_agent/dispatch.py). Console has no dispatch, so it
takes `--clinic <id>` (or uses the only clinic in the database) and
`--language`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from livekit.agents import AgentServer, JobContext, WorkerOptions, cli

from clinic_agent import heartbeat
from clinic_agent.agent import ClinicAgent
from clinic_agent.call_limit import end_after
from clinic_agent.call_record import CallRecorder, stack_of
from clinic_agent.config import ConfigError, load_settings
from clinic_agent.context import clinic_now, load_clinic, local_clinic
from clinic_agent.dispatch import AGENT_NAME, BadDispatch, CallFor, Language, call_from, language_of
from clinic_agent.prompts import build_instructions
from clinic_agent.providers import build_llm, build_stt, build_tts
from clinic_agent.session import build_session
from clinic_agent.store.db import sessions_for
from clinic_agent.store.migrations import SchemaOutdated
from clinic_agent.store.repo import NotFound
from clinic_agent.tools.booking import ClinicLink, booking_tools
from clinic_agent.tools.call import end_call_tool
from clinic_agent.tools.speech import keep_promises

logger = logging.getLogger("clinic-agent")

CONSOLE = sys.argv[1:2] == ["console"]
# `console --text` is the cheap testing mode: no speech providers are built.
# Console jobs run in this same process, so the entrypoint can read it.
TEXT_ONLY = CONSOLE and "--text" in sys.argv
# The clinic and language a console call is for, set at boot. Always None
# under dev and start: those calls run in child processes and must name both.
LOCAL_CALL: CallFor | None = None


def _take_flag(argv: list[str], name: str) -> str | None:
    """Remove `--name V` / `--name=V` from argv (LiveKit's CLI rejects
    unknown flags) and return V. Both flags are console-only: dev and start
    calls name their clinic and language in the dispatch."""
    flag = f"--{name}"
    for i, arg in enumerate(argv):
        if arg == flag or arg.startswith(f"{flag}="):
            value = arg.partition("=")[2] or (argv[i + 1] if i + 1 < len(argv) else "")
            del argv[i : i + (1 if "=" in arg else 2)]
            if not CONSOLE:
                raise ValueError(f"{flag} is for console only; dev and start calls name their {name}")
            return value
    return None


def _take_clinic_flag(argv: list[str]) -> int | None:
    value = _take_flag(argv, "clinic")
    if value is not None and not value.isdigit():
        raise ValueError(f"--clinic needs a clinic id, got {value!r}")
    return None if value is None else int(value)


def _take_language_flag(argv: list[str]) -> Language:
    value = _take_flag(argv, "language")
    try:
        return language_of("hi" if value is None else value)
    except BadDispatch as err:
        raise ValueError(f"--language: {err}") from None


def make_server() -> AgentServer:
    """The worker, registered as AGENT_NAME (explicit dispatch: it joins only
    rooms a call pass dispatches it to). LiveKit deprecated passing the name
    in code; livekit.toml is no substitute, since `dev` ignores it and `start`
    reads it from whatever folder it runs in, and a worker with no name joins
    every room. LIVEKIT_AGENT_NAME is read in every mode, and setting it here
    keeps the one name the call passes use."""
    os.environ["LIVEKIT_AGENT_NAME"] = AGENT_NAME
    return AgentServer.from_server_options(WorkerOptions(entrypoint_fnc=entrypoint))


async def entrypoint(ctx: JobContext) -> None:
    cfg = load_settings()

    try:
        call = call_from(ctx.job.metadata, fallback=LOCAL_CALL)
        clinic, time_off = await asyncio.to_thread(load_clinic, cfg, call.clinic_id)
    except (BadDispatch, NotFound) as err:
        # Never answer on a guess: a wrong clinic means wrong doctors and
        # wrong bookings; a wrong language means a caller who can't follow.
        logger.error("refusing call in room %s: %s", ctx.room.name, err)
        ctx.shutdown(reason=f"bad dispatch: {err}")
        return
    if not clinic.active:
        # Paused in the admin panel: its call page already says so; a call
        # that got through anyway (an old tab) is not answered.
        logger.warning("refusing call in room %s: clinic %s is paused", ctx.room.name, clinic.id)
        ctx.shutdown(reason="clinic paused")
        return
    logger.info("clinic %s: %s, language %s", clinic.id, clinic.name, call.language)
    instructions = build_instructions(clinic, time_off, clinic_now(clinic.timezone))
    sessions = sessions_for(cfg.database_url)
    session = build_session(cfg, text_only=TEXT_ONLY)
    stack = stack_of(session, cfg.stt_provider, cfg.llm_provider, cfg.tts_provider, TEXT_ONLY)
    record = CallRecorder(sessions, clinic.id, ctx.room.name, stack)
    await record.start()
    record.attach(session)
    ctx.add_shutdown_callback(record.finish)

    link = ClinicLink(clinic.id, clinic.timezone, sessions, on_change=record.on_change)
    tools = [*booking_tools(link), end_call_tool()]

    if TEXT_ONLY:
        logger.info("starting text-only session: llm=%s/%s", cfg.llm_provider, session.llm.model)
    else:
        logger.info(
            "starting session: stt=%s/%s llm=%s/%s tts=%s/%s",
            cfg.stt_provider, session.stt.model,
            cfg.llm_provider, session.llm.model,
            cfg.tts_provider, session.tts.model,
        )
    keep_promises(session, [t.info.name for t in tools if t.info.name != "end_call"])
    # record=False: no audio, transcript or trace goes to LiveKit Cloud, whatever
    # the project's setting says. Our own record (above) keeps the transcript
    # as text only; audio is never stored anywhere.
    await session.start(agent=ClinicAgent(instructions, tools), room=ctx.room, record=False)

    limit = asyncio.create_task(
        end_after(session, ctx, cfg.max_call_minutes * 60, on_limit=lambda: record.mark("time_limit"))
    )

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
        language = _take_language_flag(sys.argv)
        cfg = load_settings()
        build_llm(cfg)
        if not TEXT_ONLY:
            build_stt(cfg), build_tts(cfg)
        sessions_for(cfg.database_url)
        if CONSOLE:
            LOCAL_CALL = CallFor(local_clinic(cfg, requested), language)
    except NotFound as err:
        sys.exit(f"configuration error: {err}")
    except (ConfigError, SchemaOutdated, ValueError) as err:
        sys.exit(f"configuration error: {err}")

    server = make_server()
    if not CONSOLE:
        # dev and start answer patients: check in, so the dashboards can tell when they stop.
        heartbeat.attach(server, sessions_for(cfg.database_url))
    cli.run_app(server)
