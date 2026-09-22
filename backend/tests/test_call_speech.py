"""What the caller hears around tool calls, through a real AgentSession with a
scripted LLM: "one moment" while a lookup runs (unless the model already
said something), and a spoken goodbye before every hang-up."""

import asyncio

import pytest
from livekit.agents import AgentSession

from clinic_agent.agent import ClinicAgent
from clinic_agent.store import migrations
from clinic_agent.store.db import make_engine, session_factory
from clinic_agent.tools.booking import ClinicLink, booking_tools
from clinic_agent.tools.call import FALLBACK_GOODBYE, end_call_tool
from clinic_agent.tools.speech import FILLERS, keep_promises
from seeds.demo_clinic import seed_demo
from tests.fake_llm import FakeLLM, Reply
from tests.test_booking_tools import next_working_day

DAY = next_working_day().isoformat()
FIND = ("find_available_slots", {"date": DAY, "doctor_name": "Asha"})


@pytest.fixture
def link(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/speech.db")
    migrations.upgrade(engine)
    sessions = session_factory(engine)
    with sessions() as s:
        clinic_id = seed_demo(s)
    return ClinicLink(clinic_id, "Asia/Kolkata", sessions)


async def call(link, replies, user_input, greet=False):
    """Run one caller turn. Returns (what say() spoke, whether the session closed)."""
    fake = FakeLLM(replies)
    agent = ClinicAgent("test", [*booking_tools(link), end_call_tool()])
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

async def test_silent_model_gets_a_filler_in_the_callers_language(link):
    spoken, fake, _ = await call(link, [Reply(calls=[FIND]), Reply("दस बजे खाली है।")], "कल आशा जी का टाइम?")
    (text, kwargs), = spoken
    assert text in FILLERS[True] and kwargs == {"add_to_chat_ctx": False}
    # the tool still ran and its result reached the model
    assert "free start times" in fake.requests[-1].items[-1].output


async def test_english_caller_gets_an_english_filler(link):
    spoken, _, _ = await call(link, [Reply(calls=[FIND]), Reply("Ten is free.")], "Any time with Dr Asha tomorrow?")
    (text, _), = spoken
    assert text in FILLERS[False]


async def test_no_filler_when_the_model_already_said_it(link):
    replies = [Reply("ठीक है, मैं चेक करके बताती हूँ।", calls=[FIND]), Reply("दस बजे खाली है।")]
    spoken, _, _ = await call(link, replies, "कल आशा जी का टाइम?")
    assert spoken == []


async def test_two_lookups_in_one_reply_say_it_once(link):
    other = ("find_available_slots", {"date": DAY, "doctor_name": "Rohan"})
    spoken, _, _ = await call(link, [Reply(calls=[FIND, other]), Reply("...")], "कल किसी का भी टाइम?")
    assert len(spoken) == 1


# ---------- a promise to check is kept ----------

async def test_saying_it_will_check_without_a_tool_forces_the_tool(link):
    # Seen live: "मैं कल के स्लॉट्स चेक कर लेती हूँ", no tool call, then silence.
    replies = [Reply("जी, मैं कल के खाली स्लॉट्स चेक कर लेती हूँ।"), Reply(calls=[FIND]), Reply("कल नौ बजे खाली है।")]
    spoken, fake, _ = await call(link, replies, "मुझे ठीक से दिख नहीं रहा, कल दिखाना है")
    assert fake.replies == [], "the follow-up and the answer after the tool never ran"
    assert "free start times" in fake.requests[2].items[-1].output
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


async def test_an_empty_goodbye_still_says_goodbye(link):
    spoken, _, closed = await call(link, [Reply(calls=[("end_call", {"goodbye": "  "})])], "bye")
    assert spoken == [(FALLBACK_GOODBYE[False], {"allow_interruptions": False})]
    assert closed
