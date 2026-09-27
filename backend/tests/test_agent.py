"""The agent's own behaviour outside any tool."""

from clinic_agent.agent import ClinicAgent


class _Session:
    def __init__(self):
        self.replies = []

    def generate_reply(self, **kwargs):
        self.replies.append(kwargs)


async def test_the_greeting_can_call_no_tool(monkeypatch):
    session = _Session()
    monkeypatch.setattr(ClinicAgent, "session", property(lambda self: session))
    await ClinicAgent("instructions").on_enter()
    assert session.replies == [{"tool_choice": "none"}]
