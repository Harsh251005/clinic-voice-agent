"""The agent's behaviour: persona now, tools later.

This is where `@function_tool` methods attach in Stage 2. Nothing about the
speech pipeline lives here.
"""

from __future__ import annotations

from livekit.agents import Agent

from clinic_agent.prompts import SYSTEM_PROMPT


class ClinicAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

    async def on_enter(self) -> None:
        """Speak first, the way a receptionist picks up the phone."""
        self.session.generate_reply()
