"""The agent a call gets: every tool present, end_call hidden during the greeting."""

from livekit.agents.llm import ToolFlag

from clinic_agent.agent import ClinicAgent
from clinic_agent.tools.booking import ClinicLink, booking_tools
from clinic_agent.tools.call import GOODBYE, end_call_tool


def _names(agent):
    names = []
    for tool in agent.tools:
        names += [t.info.name for t in getattr(tool, "tools", [tool])]
    return names


def test_call_agent_has_booking_and_end_call_tools():
    tools = [*booking_tools(ClinicLink(1, "Asia/Kolkata", sessions=None)), end_call_tool()]
    agent = ClinicAgent("instructions", tools)
    assert sorted(_names(agent)) == ["book_appointment", "end_call", "find_available_slots"]


def test_end_call_cannot_fire_during_greeting():
    (tool,) = end_call_tool().tools
    assert tool.info.flags & ToolFlag.IGNORE_ON_ENTER


def test_goodbye_follows_the_script_rules():
    assert "same script rules" in GOODBYE
