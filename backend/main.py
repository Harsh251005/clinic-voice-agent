"""Clinic voice agent.

    uv run python main.py console   talk to it locally (no LiveKit minutes)
    uv run python main.py console --text
                                    type to it: LLM only, no STT/TTS cost
    uv run python main.py dev       join LiveKit rooms it is dispatched to (restart it after a code change)
    uv run python main.py start     production worker

One worker answers for every clinic: each call's dispatch names its clinic
and language (see clinic_agent/dispatch.py; Hindi is the only line). Console
has no dispatch, so it takes `--clinic <id>` (or uses the only clinic in the
database) and answers in Hindi.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from livekit.agents import AgentServer, JobContext, WorkerOptions, cli

from clinic_agent import heartbeat
from clinic_agent.call_limit import end_after
from clinic_agent.call_setup import ClinicPaused, LineOff, prepare
from clinic_agent.config import ConfigError, load_settings, refuse_moved_settings
from clinic_agent.context import every_clinics_settings, local_clinic
from clinic_agent.dispatch import AGENT_NAME, LANGUAGES, BadDispatch, CallFor, call_from
from clinic_agent.lines import NAMES, available
from clinic_agent.store.db import sessions_for
from clinic_agent.store.migrations import SchemaOutdated
from clinic_agent.store.repo import NotFound

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
    unknown flags) and return V. Console-only: dev and start calls name
    their clinic in the dispatch."""
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


def _refuse_language_flag(argv: list[str]) -> None:
    """`--language` chose English or Hindi; Hindi is the only line now."""
    if _take_flag(argv, "language") is not None:
        raise ValueError("--language is gone: every call is in Hindi (the only line)")


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
        # The call itself is put together in call_setup.py, shared with the
        # admin's typed chat so the two can't drift apart.
        ready = await prepare(cfg, call, ctx.room.name, text_only=TEXT_ONLY)
    except (BadDispatch, NotFound) as err:
        # Never answer on a guess: a wrong clinic means wrong doctors and
        # wrong bookings; a wrong language means a caller who can't follow.
        logger.error("refusing call in room %s: %s", ctx.room.name, err)
        ctx.shutdown(reason=f"bad dispatch: {err}")
        return
    except ClinicPaused as err:
        # Paused in the admin panel: its call page already says so; a call
        # that got through anyway (an old tab) is not answered.
        logger.warning("refusing call in room %s: %s", ctx.room.name, err)
        ctx.shutdown(reason="clinic paused")
        return
    except LineOff as err:
        # Its key is missing: the call page no longer offers this line, so
        # only a page opened before the worker started can get here.
        logger.error("refusing call in room %s: %s", ctx.room.name, err)
        ctx.shutdown(reason=f"line off: {call.language}")
        return
    session, record, phrases = ready.session, ready.record, ready.phrases
    ctx.add_shutdown_callback(record.finish)
    # record=False: no audio, transcript or trace goes to LiveKit Cloud, whatever
    # the project's setting says. Our own record keeps the transcript
    # as text only; audio is never stored anywhere.
    await session.start(agent=ready.agent, room=ctx.room, record=False)

    limit = asyncio.create_task(end_after(
        session, ctx, ready.cfg.max_call_minutes * 60, phrases.one("goodbye_time_limit", call.language),
        on_limit=lambda: record.mark("time_limit"),
    ))

    async def _stop_limit() -> None:
        limit.cancel()

    ctx.add_shutdown_callback(_stop_limit)


if __name__ == "__main__":
    # Fail before the worker starts rather than on the first call, and report
    # it as a one-line setup error instead of a traceback. Trying each
    # language line's providers here finds a missing key: that line is off.
    # Hindi is the only line, so a missing key leaves nothing to answer calls
    # and it exits (with a second line, the other would still answer). The session
    # itself needs a running event loop, so it is left to the entrypoint.
    # Opening the database here catches an old schema; console also resolves
    # its clinic, since it has no dispatch to name one.
    try:
        requested = _take_clinic_flag(sys.argv)
        _refuse_language_flag(sys.argv)
        cfg = load_settings()
        refuse_moved_settings()
        sessions_for(cfg.database_url)  # an old schema stops here, before reading the settings
        # Each clinic's own voice: a line is off only if no clinic can use it.
        checks = [(name, available(call.cfg, TEXT_ONLY)) for name, call in every_clinics_settings(cfg)]
        lines_off = {}
        for lang in LANGUAGES:
            whys = [(name, found[lang]) for name, found in checks if found[lang]]
            if len(whys) == len(checks):
                lines_off[lang] = whys[0][1]
            for name, why in whys if len(whys) < len(checks) else []:
                print(f"warning: {name}'s calls can't be answered: {why}", file=sys.stderr)
        ready = [lang for lang in LANGUAGES if lang not in lines_off]
        if not ready:
            raise ConfigError("no language line can take calls: " + "; ".join(
                f"{NAMES[lang]}: {why}" for lang, why in lines_off.items()))
        sessions_for(cfg.database_url)
        if CONSOLE:
            LOCAL_CALL = CallFor(local_clinic(cfg, requested), "hi")
    except NotFound as err:
        sys.exit(f"configuration error: {err}")
    except (ConfigError, SchemaOutdated, ValueError) as err:
        sys.exit(f"configuration error: {err}")
    for lang, why in lines_off.items():
        print(f"warning: the {NAMES[lang]} line is off, calls in {NAMES[lang]} won't be offered: {why}",
              file=sys.stderr)

    server = make_server()
    if not CONSOLE:
        # dev and start answer patients: check in, so the dashboards can tell when they stop.
        heartbeat.attach(server, sessions_for(cfg.database_url), ready)
    cli.run_app(server)
