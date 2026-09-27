"""The agent's behaviour: its instructions and the tools it may call.

Both are built per call by the entrypoint (instructions from the clinic's
data in prompts.py, tools from clinic_agent.tools). Nothing about the speech
pipeline lives here.
"""

from __future__ import annotations

from livekit.agents import Agent, llm


class ClinicAgent(Agent):
    def __init__(
        self, instructions: str, tools: list[llm.Tool | llm.Toolset] | None = None
    ) -> None:
        super().__init__(instructions=instructions, tools=tools or [])

    async def on_enter(self) -> None:
        """Speak first, the way a receptionist picks up the phone. No tools on
        this turn: nobody has asked for anything yet (seen live: the greeting
        looked up tomorrow evening's slots and offered them unprompted)."""
        self.session.generate_reply(tool_choice="none")
