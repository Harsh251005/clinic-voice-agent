"""Putting one call together: the clinic's settings, its instructions, the
session, the tools, the fixed phrases, the record and the agent.

The worker (main.py) and the admin's typed chat (clinic_agent/chats.py) both
build their call here and nowhere else, so a chat answers exactly as a call
would: same rules and clinic facts, same brain and settings, same tools and
booking code, same record. What differs is only around it: a call has a room
and a voice, a chat has neither.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from livekit.agents import AgentSession

from clinic_agent import voice_clips
from clinic_agent.agent import ClinicAgent
from clinic_agent.call_record import CallRecorder, stack_of
from clinic_agent.config import ConfigError, Settings
from clinic_agent.context import clinic_now, load_clinic
from clinic_agent.dispatch import CallFor
from clinic_agent.lines import NAMES, line_for
from clinic_agent.pauses import wait_for_numbers
from clinic_agent.prompts import build_instructions
from clinic_agent.session import build_session
from clinic_agent.store.db import sessions_for
from clinic_agent.store.models import Clinic
from clinic_agent.tools.booking import ClinicLink, booking_tools
from clinic_agent.tools.call import end_call_tool
from clinic_agent.tools.speech import keep_promises
from clinic_agent.voice_clips import Phrasebook

logger = logging.getLogger("clinic-agent")


class ClinicPaused(Exception):
    """Paused in the admin panel: its calls are not answered."""


class LineOff(Exception):
    """The call's line can't answer: a missing key, or a voice the vendor refuses."""


@dataclass
class Prepared:
    """A call ready to start: `await session.start(agent=agent, ...)`."""
    cfg: Settings  # the dashboard's settings for this call (call_settings.py)
    clinic: Clinic
    session: AgentSession
    agent: ClinicAgent
    record: CallRecorder
    phrases: Phrasebook


async def prepare(cfg: Settings, call: CallFor, room: str, *, text_only: bool = False) -> Prepared:
    """Everything for one call to `call.clinic_id`, its record already open.

    Raises repo.NotFound (no such clinic), ClinicPaused or LineOff: never
    answer on a guess. `text_only` builds just the brain (typed in, text out).
    """
    clinic, time_off, settings = await asyncio.to_thread(load_clinic, cfg, call.clinic_id)
    if not clinic.active:
        raise ClinicPaused(f"clinic {clinic.id} is paused")
    cfg = settings.cfg  # the dashboard's settings from here on
    line = line_for(cfg, call.language)
    try:
        session = build_session(cfg, line, text_only=text_only)
    except (ConfigError, ValueError) as err:  # a missing key, or a voice the vendor refuses
        raise LineOff(f"the {NAMES[call.language]} line is off: {err}") from err
    logger.info("clinic %s: %s, %s line%s", clinic.id, clinic.name, NAMES[call.language], " (test call)" if call.test else "")
    instructions = build_instructions(clinic, time_off, clinic_now(clinic.timezone), call.language, settings.rules)
    sessions = sessions_for(cfg.database_url)
    stack = stack_of(session, line, text_only)
    record = CallRecorder(sessions, clinic.id, room, stack, call.language, call.test, line)
    await record.start()
    record.attach(session)

    wait_for_numbers(session, cfg.min_endpointing_delay, cfg.number_endpointing_delay)
    # The greeting, fillers and fixed goodbyes, each with its recording for this
    # voice when an admin has recorded one; anything missing is said live.
    phrases = await asyncio.to_thread(
        voice_clips.for_call, sessions, clinic, call.language, None if text_only else session.tts)
    phrases.on_play = record.clip_played  # the trace notes each line played from a recording
    link = ClinicLink(
        clinic.id, clinic.timezone, sessions, call.language, phrases,
        on_change=record.on_change, on_give_up=record.gave_up,
    )
    tools = [*booking_tools(link), end_call_tool(call.language, phrases)]
    logger.info("starting session: %s", stack)
    keep_promises(session, [t.info.name for t in tools if t.info.name != "end_call"])
    agent = ClinicAgent(instructions, tools, phrases, call.language, settings.greeting_interruptible)
    return Prepared(cfg, clinic, session, agent, record, phrases)
