"""What the caller hears around tool calls, through a real AgentSession with a
scripted LLM: "one moment" while a lookup runs (unless the model already
said something), and a spoken goodbye before every hang-up."""

import asyncio
import dataclasses

import pytest
from livekit.agents import AgentSession

from clinic_agent.agent import ClinicAgent
from clinic_agent.store import migrations
from clinic_agent.store.db import make_engine, session_factory
from clinic_agent.tools.booking import ClinicLink, booking_tools
from clinic_agent.tools.call import end_call_tool
from clinic_agent.tools.speech import keep_promises
from clinic_agent.voice_clips import BUILT_IN

FILLERS = BUILT_IN[("filler", "hi")]
FALLBACK_GOODBYE = BUILT_IN[("goodbye_fallback", "hi")][0]
from seeds.demo_clinic import seed_demo
from tests.fake_llm import FakeLLM, Reply
from tests.test_booking_tools import next_working_day

DAY = next_working_day().isoformat()
FIND = ("find_available_slots", {"date": DAY, "reason_fits": "none", "doctor_name": "Asha"})


@pytest.fixture
def link(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/speech.db")
    migrations.upgrade(engine)
    sessions = session_factory(engine)
    with sessions() as s:
        clinic_id = seed_demo(s)
    return ClinicLink(clinic_id, "Asia/Kolkata", sessions, "hi")


async def call(link, replies, user_input, greet=False):
    """Run one caller turn. Returns (what say() spoke, whether the session closed)."""
    fake = FakeLLM(replies)
    agent = ClinicAgent("test", [*booking_tools(link), end_call_tool(link.language)])
    agent.on_enter = _silent  # no greeting: the first scripted reply answers the caller
    spoken, closed = [], []
    async with AgentSession(llm=fake) as session:
        real_say = session.say

        def say(text, **kwargs):
            spoken.append((text, kwargs))
            return real_say(text, **kwargs)

        session.say = say
        session.on("close", lambda ev: closed.append(ev))
        keep_promises(session, [t.info.name for t in booking_tools(link)])
        await session.start(agent)
        await session.run(user_input=user_input)
        for _ in range(100):  # a forced follow-up starts after run() returns
            if not fake.replies:
                break
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.1)
        await session.aclose()
    return spoken, fake, closed


async def _silent():
    return None


# ---------- "one moment" during a lookup ----------

async def test_silent_model_gets_a_filler_in_the_calls_language(link):
    spoken, fake, _ = await call(link, [Reply(calls=[FIND]), Reply("दस बजे खाली है।")], "कल आशा जी का टाइम?")
    (text, kwargs), = spoken
    assert text in FILLERS and kwargs == {"add_to_chat_ctx": False}
    # the tool still ran and its result reached the model
    assert "offer these free times" in fake.requests[-1].items[-1].output


async def test_a_hindi_call_keeps_its_hindi_filler_when_the_caller_speaks_english(link):
    # The voice speaks only the call's language, not the caller's last words.
    spoken, _, _ = await call(link, [Reply(calls=[FIND]), Reply("दस बजे खाली है।")], "Any time with Dr Asha tomorrow?")
    (text, _), = spoken
    assert text in FILLERS


async def test_a_recorded_filler_plays_its_recording(link):
    from clinic_agent.voice_clips import Phrasebook, Said

    book = Phrasebook({("filler", "hi"): [Said("जी, बस एक सेकंड।", b"\x00\x00" * 2400, 24000, kind="filler")]})
    played = []
    book.on_play = played.append  # what the call's trace is told
    recorded = dataclasses.replace(link, phrases=book)
    spoken, fake, _ = await call(recorded, [Reply(calls=[FIND]), Reply("दस बजे खाली है।")], "कल आशा जी का टाइम?")
    (text, kwargs), = spoken
    assert text == "जी, बस एक सेकंड।" and kwargs["add_to_chat_ctx"] is False and "audio" in kwargs
    assert played == ["filler"]  # the trace notes it came from a recording (no voice cost)
    assert "offer these free times" in fake.requests[-1].items[-1].output


async def test_an_empty_goodbye_plays_the_recorded_one(link):
    from clinic_agent.voice_clips import Phrasebook, Said

    book = Phrasebook({("goodbye_fallback", "hi"): [Said("धन्यवाद, नमस्ते!", b"\x00\x00" * 2400, 24000)]})
    fake = FakeLLM([Reply(calls=[("end_call", {"goodbye": ""})])])
    agent = ClinicAgent("test", [end_call_tool("hi", book)])
    agent.on_enter = _silent
    spoken, closed = [], []
    async with AgentSession(llm=fake) as session:
        real_say = session.say

        def say(text, **kwargs):
            spoken.append((text, kwargs))
            return real_say(text, **kwargs)

        session.say = say
        session.on("close", lambda ev: closed.append(ev))
        await session.start(agent)
        await session.run(user_input="bye")
        await asyncio.sleep(0.1)
    (text, kwargs), = spoken
    assert text == "धन्यवाद, नमस्ते!" and kwargs["allow_interruptions"] is False and "audio" in kwargs
    assert closed


async def test_no_filler_when_the_model_already_said_it(link):
    replies = [Reply("ठीक है, मैं चेक करके बताती हूँ।", calls=[FIND]), Reply("दस बजे खाली है।")]
    spoken, _, _ = await call(link, replies, "कल आशा जी का टाइम?")
    assert spoken == []


async def test_two_lookups_in_one_reply_say_it_once(link):
    other = ("find_available_slots", {"date": DAY, "reason_fits": "none", "doctor_name": "Rohan"})
    spoken, _, _ = await call(link, [Reply(calls=[FIND, other]), Reply("...")], "कल किसी का भी टाइम?")
    assert len(spoken) == 1


# ---------- a promise to check is kept ----------

async def test_saying_it_will_check_without_a_tool_forces_the_tool(link):
    # Seen live: "मैं कल के स्लॉट्स चेक कर लेती हूँ", no tool call, then silence.
    replies = [Reply("जी, मैं कल के खाली स्लॉट्स चेक कर लेती हूँ।"), Reply(calls=[FIND]), Reply("कल नौ बजे खाली है।")]
    spoken, fake, _ = await call(link, replies, "मुझे ठीक से दिख नहीं रहा, कल दिखाना है")
    assert fake.replies == [], "the follow-up and the answer after the tool never ran"
    assert "offer these free times" in fake.requests[2].items[-1].output
    assert spoken == []  # the promise itself was the "one moment": no second filler


@pytest.mark.parametrize("line", [
    "क्या मैं कल के स्लॉट्स चेक करूँ?",   # a question: the caller answers next
    "आँखों का चेकअप कल सुबह होता है।",      # a check-up, not a promise
    "कल डॉक्टर उपलब्ध हैं, कौन सा टाइम चाहिए?",
])
async def test_other_replies_are_left_alone(link, line):
    _, fake, _ = await call(link, [Reply(line), Reply("SHOULD NOT RUN")], "कल?")
    assert len(fake.requests) == 1 and fake.replies == [Reply("SHOULD NOT RUN")]


async def test_a_forced_follow_up_is_not_forced_again(link):
    promise = Reply("मैं चेक करके बताती हूँ।")
    _, fake, _ = await call(link, [promise, promise, Reply("SHOULD NOT RUN")], "कल?")
    assert len(fake.requests) == 2


# ---------- goodbye before hanging up ----------

async def test_end_call_speaks_the_goodbye_then_hangs_up(link):
    goodbye = "आपका अपॉइंटमेंट कल सुबह दस बजे बुक है। धन्यवाद, नमस्ते!"
    spoken, fake, closed = await call(link, [Reply(calls=[("end_call", {"goodbye": goodbye})])], "बस इतना ही, धन्यवाद")
    assert spoken == [(goodbye, {"allow_interruptions": False})]
    assert closed, "session was not closed after the goodbye"
    assert len(fake.requests) == 1  # no second model round after the tool


async def test_an_empty_goodbye_still_says_goodbye_in_hindi(link):
    spoken, _, closed = await call(link, [Reply(calls=[("end_call", {"goodbye": "  "})])], "bye")
    assert spoken == [(FALLBACK_GOODBYE, {"allow_interruptions": False})]
    assert closed


# ---------- a lookup that can't answer: the code says so, never the model ----------
# Seen 2026-11-10 (call 37): ten lookups failed and the model made up free times.

from clinic_agent import booking  # noqa: E402
from clinic_agent.store import repo  # noqa: E402

SORRY = BUILT_IN[("sorry_cant_check", "hi")][0]
NOBODY = ("find_available_slots", {"date": DAY, "reason_fits": "none", "doctor_name": "Dr. Sharma"})
MADE_UP = Reply("पाँच बजे का टाइम खाली है।")  # what the model would say next: it must never get the turn


def _problems(link):
    with link.sessions() as s:
        return [(i.subject, i.detail) for i in repo.open_incidents(s) if i.kind == "tools_failing"]


async def test_the_same_error_twice_running_is_answered_by_the_code(link):
    spoken, fake, _ = await call(link, [Reply(calls=[NOBODY]), Reply(calls=[NOBODY]), MADE_UP], "डॉक्टर शर्मा का टाइम?")
    assert SORRY in [text for text, _ in spoken]
    assert fake.replies == [MADE_UP] and len(fake.requests) == 2  # the model was not asked again
    # the admin is told which step and why, never the error's words (they can hold a caller's)
    assert _problems(link) == [("find_available_slots", "same error twice running")]


async def test_one_error_still_goes_to_the_model_to_put_right(link):
    spoken, fake, _ = await call(link, [Reply(calls=[NOBODY]), Reply(calls=[FIND]), Reply("दस बजे खाली है।")], "टाइम?")
    assert SORRY not in [text for text, _ in spoken] and not fake.replies
    assert "Nothing was checked" in fake.requests[1].items[-1].output  # told not to guess meanwhile
    assert _problems(link) == []


async def test_a_crashed_lookup_is_answered_by_the_code(link, monkeypatch):
    def crash(*args):
        raise RuntimeError("the caller said 9876543210")

    monkeypatch.setattr(booking, "find_slots", crash)
    spoken, fake, _ = await call(link, [Reply(calls=[FIND]), MADE_UP], "कल आशा जी का टाइम?")
    assert SORRY in [text for text, _ in spoken]
    assert fake.replies == [MADE_UP]
    assert _problems(link) == [("find_available_slots", "crashed: RuntimeError")]


async def test_the_problem_closes_once_that_lookup_works_on_a_call(link, monkeypatch):
    with monkeypatch.context() as broken:
        broken.setattr(booking, "find_slots", lambda *a: 1 / 0)
        await call(link, [Reply(calls=[FIND]), MADE_UP], "कल आशा जी का टाइम?")
    assert _problems(link)
    await call(link, [Reply(calls=[FIND]), Reply("दस बजे खाली है।")], "कल आशा जी का टाइम?")
    assert _problems(link) == []
