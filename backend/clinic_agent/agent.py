"""The agent's behaviour: its instructions and the tools it may call.

Both are built per call by the entrypoint (instructions from the clinic's
data in prompts.py, tools from clinic_agent.tools). Nothing about the speech
pipeline lives here.
"""

from __future__ import annotations

from livekit.agents import Agent, llm

from clinic_agent import voice_clips
from clinic_agent.voice_clips import Phrasebook


class ClinicAgent(Agent):
    def __init__(
        self, instructions: str, tools: list[llm.Tool | llm.Toolset] | None = None,
        phrases: Phrasebook | None = None, language: str = "hi", greeting_interruptible: bool = False,
    ) -> None:
        super().__init__(instructions=instructions, tools=tools or [])
        self._greeting = (phrases or Phrasebook()).one("greeting", language)
        self._greeting_interruptible = greeting_interruptible

    async def on_enter(self) -> None:
        """Speak first, the way a receptionist picks up the phone: the clinic's
        fixed greeting (its recording when there is one), never written by the
        model, so no model round and no tools before the caller speaks. The
        caller can't cut it off (Harsh, 2026-11-09) unless the admin allows
        it for every clinic (Admin > Receptionist, 2026-11-10)."""
        voice_clips.say(self.session, self._greeting, allow_interruptions=self._greeting_interruptible)
