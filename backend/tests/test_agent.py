"""The agent's own behaviour outside any tool."""

from clinic_agent.agent import ClinicAgent
from clinic_agent.voice_clips import Phrasebook, Said


class _Session:
    def __init__(self):
        self.replies, self.said = [], []

    def generate_reply(self, **kwargs):
        self.replies.append(kwargs)

    def say(self, text, **kwargs):
        self.said.append((text, kwargs))


async def _greet(monkeypatch, phrases=None):
    session = _Session()
    monkeypatch.setattr(ClinicAgent, "session", property(lambda self: session))
    await ClinicAgent("instructions", phrases=phrases).on_enter()
    return session


async def test_the_greeting_is_the_fixed_one_and_cannot_be_cut_off(monkeypatch):
    # No model round before the caller speaks (no tools, no invented greeting), and
    # the caller's voice can't stop it: it tells them the call is automated and saved.
    book = Phrasebook({("greeting", "hi"): [Said("नमस्ते, क्लिनिक में आपका स्वागत है।")]})
    session = await _greet(monkeypatch, book)
    assert session.replies == []
    assert session.said == [("नमस्ते, क्लिनिक में आपका स्वागत है।", {"allow_interruptions": False})]


async def test_a_recorded_greeting_plays_its_recording(monkeypatch):
    book = Phrasebook({("greeting", "hi"): [Said("नमस्ते", b"\x00\x00" * 2400, 24000)]})
    (text, kwargs), = (await _greet(monkeypatch, book)).said
    assert text == "नमस्ते" and kwargs["allow_interruptions"] is False and "audio" in kwargs


async def test_without_a_phrasebook_the_built_in_greeting_is_said(monkeypatch):
    (text, _), = (await _greet(monkeypatch)).said
    assert "ऑटोमेटेड असिस्टेंट" in text
