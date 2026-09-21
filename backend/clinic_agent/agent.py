"""The agent's behaviour: instructions now, tools next.

Instructions are built per call from the clinic's data (see prompts.py), so
the agent is constructed by the entrypoint with them. Nothing about the
speech pipeline lives here.
"""

from __future__ import annotations

from livekit.agents import Agent


class ClinicAgent(Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)

    async def on_enter(self) -> None:
        """Speak first, the way a receptionist picks up the phone."""
        self.session.generate_reply()
