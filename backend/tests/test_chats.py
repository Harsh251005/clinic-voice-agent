"""An admin's typed chat is a real call without a voice: built by the same
code as the worker's, booked through the real tools, recorded as a test call
that spent no LiveKit minutes, and ended like a call."""

import asyncio

import pytest
from livekit.agents import AgentSession

from clinic_agent import call_setup
from clinic_agent.call_setup import ClinicPaused, prepare
from clinic_agent.chats import Chats, NotNow, TooManyChats
from clinic_agent.config import load_settings
from clinic_agent.dispatch import CallFor
from clinic_agent.store import migrations, repo
from clinic_agent.store.db import make_engine, session_factory, sessions_for
from clinic_agent.store.models import Call, CallTranscript, Usage
from seeds.demo_clinic import seed_demo
from tests.fake_llm import FakeLLM, Reply
from tests.test_booking_readback import BOOK, CHECK, DAY
from tests.test_call_record import PHONE


@pytest.fixture
def clinic(env, tmp_path):
    url = f"sqlite:///{tmp_path}/chats.db"
    engine = make_engine(url)
    migrations.upgrade(engine)
    with session_factory(engine)() as s:
        clinic_id = seed_demo(s)
    env.setenv("DATABASE_URL", url)
    return clinic_id


@pytest.fixture
def brain(monkeypatch):
    """Script the brain: `brain(Reply(...), ...)` before starting a chat."""
    def script(*replies):
        fake = FakeLLM(list(replies))
        monkeypatch.setattr(call_setup, "build_session", lambda cfg, line, text_only=False: AgentSession(llm=fake))
        return fake
    return script


async def settled(chat, *, ended=False):
    for _ in range(400):
        if chat.ended if ended else not chat.replying:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the chat never settled")


def saved(call_id):
    with sessions_for(load_settings().database_url)() as s:
        call = s.get(Call, call_id)
        usage = [(u.provider, u.unit) for u in s.query(Usage).filter_by(call_id=call_id)]
        return call, s.get(CallTranscript, call_id), usage


async def test_a_chat_greets_first_then_books_through_the_real_tools(clinic, brain):
    brain(Reply(calls=[CHECK]), Reply("डॉ. आशा मेहता, पाँच बजे, रवि, सही है?"), Reply(calls=[BOOK]), Reply("बुक हो गया।"))
    room = Chats(load_settings())
    chat = await room.start(clinic)
    assert [line["role"] for line in chat.lines] == ["agent"] and "Demo Family Clinic" in chat.lines[0]["text"]

    chat.send(f"पाँच बजे, नाम रवि, नंबर {PHONE}")
    with pytest.raises(NotNow, match="still answering"):
        chat.send("हेलो?")
    await settled(chat)
    chat.send("हाँ, सही है")
    await settled(chat)

    tools = [line for line in chat.lines if line["role"] == "tool"]
    assert [t["tool"] for t in tools] == ["check_booking", "book_appointment"] and all(t["ok"] for t in tools)
    assert PHONE in tools[0]["args"] and tools[0]["text"]  # what she sent, and what came back
    assert chat.lines[-1] == chat.lines[-1] | {"role": "agent", "text": "बुक हो गया।"}

    await chat.end()
    call, transcript, usage = saved(chat.call_id)
    assert (call.test, call.outcome, call.end_reason) == (True, "booked", "caller_left")
    assert call.room.startswith(repo.CHAT_ROOM) and call.stack.startswith("text · ")
    assert transcript.items == chat.lines
    assert all(vendor != "livekit" for vendor, _ in usage)  # no room, no LiveKit minutes
    with sessions_for(load_settings().database_url)() as s:
        assert len(repo.appointments_on(s, clinic, DAY)) == 1
        assert repo.patient_calls_since(s, call.started_at, with_tests=True) == []  # not a worker's call


async def test_end_call_ends_the_chat_with_its_goodbye(clinic, brain):
    brain(Reply(calls=[("end_call", {"goodbye": "धन्यवाद, नमस्ते।"})]))
    chat = await Chats(load_settings()).start(clinic)
    chat.send("बस इतना ही")
    await settled(chat, ended=True)
    assert "धन्यवाद, नमस्ते।" in [line["text"] for line in chat.lines if line["role"] == "agent"]
    assert chat.end_reason == "agent_ended"
    with pytest.raises(NotNow, match="ended"):
        chat.send("हेलो?")


async def test_the_clinics_longest_call_ends_a_chat(clinic, brain):
    brain()
    with sessions_for(load_settings().database_url)() as s:
        repo.get_clinic(s, clinic).max_call_minutes = 0.001
        s.commit()
    chat = await Chats(load_settings()).start(clinic)
    await settled(chat, ended=True)
    assert chat.end_reason == "time_limit"
    assert saved(chat.call_id)[0].end_reason == "time_limit"


async def test_a_quiet_chat_is_ended_and_only_so_many_run_at_once(clinic, brain):
    brain()
    room = Chats(load_settings(), most=1, idle=0)
    chat = await room.start(clinic)
    with pytest.raises(TooManyChats):
        await room.start(clinic)
    watch = asyncio.create_task(room.watch(every=0.01))
    await settled(chat, ended=True)
    watch.cancel()
    assert chat.end_reason == "caller_left"
    await (await room.start(clinic)).end()  # room again once it ended


async def test_stopping_the_server_writes_every_chats_record(clinic, brain):
    brain()
    room = Chats(load_settings())
    chat = await room.start(clinic)
    await room.close()
    assert saved(chat.call_id)[0].end_reason == "shutdown"


async def test_a_paused_clinic_gets_no_chat(clinic, brain):
    brain()
    with sessions_for(load_settings().database_url)() as s:
        repo.set_clinic_active(s, clinic, False)
    with pytest.raises(ClinicPaused):
        await Chats(load_settings()).start(clinic)


async def test_a_chat_and_a_call_get_the_same_instructions_and_tools(clinic, brain, monkeypatch):
    """The point of call_setup: the only difference is the voice around it."""
    brain()
    monkeypatch.setattr(call_setup, "stack_of", lambda *a: "stack")  # the scripted session has no ears or voice to name
    cfg = load_settings()
    as_call = await prepare(cfg, CallFor(clinic, "hi"), "call-demo-1")
    as_chat = await prepare(cfg, CallFor(clinic, "hi", test=True), f"{repo.CHAT_ROOM}1", text_only=True)
    assert as_call.agent.instructions == as_chat.agent.instructions
    names = lambda ready: [t.info.name for t in ready.agent.tools]  # noqa: E731
    assert names(as_call) == names(as_chat) and "end_call" in names(as_call)
    for ready in (as_call, as_chat):
        await ready.session.aclose()
