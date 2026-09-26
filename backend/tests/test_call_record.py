"""A call's record, through a real AgentSession with a scripted LLM: the
trace says what happened and never what was said, the transcript holds the
words, the outcome comes from what the tools changed, and recording can
never break a call. Plus the purge of expired records."""

from dataclasses import replace
from datetime import timedelta

import pytest
from livekit.agents import AgentSession

from clinic_agent.agent import ClinicAgent
from clinic_agent.call_record import CallRecorder
from clinic_agent.store import migrations, repo
from clinic_agent.store.db import make_engine, session_factory
from clinic_agent.store.models import Call, CallEvent, CallTranscript, utc_now
from clinic_agent.store.purge import TRACE_DAYS, TRANSCRIPT_DAYS, purge
from clinic_agent.tools.booking import ClinicLink, booking_tools
from seeds.demo_clinic import seed_demo
from tests.fake_llm import FakeLLM, Reply
from tests.test_booking_readback import BOOK, CHECK, DAY

PHONE = "9876543210"


@pytest.fixture
def link(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/record.db")
    migrations.upgrade(engine)
    sessions = session_factory(engine)
    with sessions() as s:
        clinic_id = seed_demo(s)
    return ClinicLink(clinic_id, "Asia/Kolkata", sessions)


async def _silent():
    return None


async def record_call(link, replies, turns, recorder=None):
    """Play the caller's turns with a recorder attached, then finish the
    record the way the job's shutdown does. Returns the recorder."""
    record = recorder or CallRecorder(link.sessions, link.clinic_id, "room-1", "text · fake/model")
    await record.start()
    agent = ClinicAgent("test", booking_tools(replace(link, on_change=record.on_change)))
    agent.on_enter = _silent
    async with AgentSession(llm=FakeLLM(replies)) as session:
        record.attach(session)
        await session.start(agent)
        for text in turns:
            await session.run(user_input=text)
        await session.aclose()
    await record.finish()
    return record


def _saved(link, call_id):
    with link.sessions() as s:
        call = s.get(Call, call_id)
        events = s.query(CallEvent).filter_by(call_id=call_id).order_by(CallEvent.id).all()
        transcript = s.get(CallTranscript, call_id)
        return call, events, transcript


BOOKING_CALL = (
    [
        Reply(calls=[CHECK]), Reply("डॉ. आशा मेहता, पाँच बजे, रवि, सही है?"),
        Reply(calls=[BOOK]), Reply("बुक हो गया।"),
    ],
    [f"पाँच बजे, नाम रवि, नंबर {PHONE}", "हाँ, सही है"],
)


async def test_a_booking_call_is_recorded_with_its_outcome_and_appointment(link):
    record = await record_call(link, *BOOKING_CALL)
    call, events, transcript = _saved(link, record.call_id)

    (appt,) = repo.appointments_on(link.sessions(), link.clinic_id, DAY)
    assert call.outcome == "booked"
    assert call.appointments == [{"id": appt.id, "action": "booked"}]
    assert call.turn_count == 2 and call.error_count == 0
    assert call.ended_at is not None and call.end_reason
    assert call.stack == "text · fake/model" and call.room == "room-1"

    tools = [(e.name, e.ok) for e in events if e.kind == "tool"]
    assert tools == [("check_booking", True), ("book_appointment", True)]
    assert all(e.duration_ms is not None for e in events if e.kind == "tool")
    assert {"llm"} <= {e.kind for e in events}  # per-turn timings from the messages

    roles = [i["role"] for i in transcript.items]
    assert roles.count("caller") == 2 and "agent" in roles and roles.count("tool") == 2
    assert transcript.items[0]["text"].startswith("पाँच बजे")
    assert transcript.purge_after == call.started_at + timedelta(days=TRANSCRIPT_DAYS)


async def test_the_trace_holds_none_of_what_was_said(link):
    record = await record_call(link, *BOOKING_CALL)
    _, events, transcript = _saved(link, record.call_id)
    trace = " ".join(f"{e.name} {e.detail}" for e in events)
    for words in (PHONE, "Ravi", "रवि", "Fever", "पाँच"):
        assert words not in trace
    # ...while the transcript has it, tool arguments included.
    assert any(PHONE in i.get("args", "") for i in transcript.items)


async def test_a_refused_tool_is_traced_as_failed_and_changes_nothing(link):
    record = await record_call(link, [Reply(calls=[BOOK]), Reply("...")], ["बुक कर दो"])
    call, events, _ = _saved(link, record.call_id)
    assert [(e.name, e.ok) for e in events if e.kind == "tool"] == [("book_appointment", False)]
    assert call.outcome == "info_only" and call.appointments == []


@pytest.mark.parametrize(("changes", "end_reason", "turns", "expected"), [
    ([{"id": 1, "action": "cancelled"}, {"id": 2, "action": "booked"}], "agent_ended", 3, "booked"),
    ([{"id": 1, "action": "moved"}], "caller_left", 2, "moved"),
    ([{"id": 1, "action": "cancelled"}], "agent_ended", 2, "cancelled"),
    ([], "error", 1, "failed"),
    ([], "caller_left", 0, "no_action"),
    ([], "agent_ended", 2, "info_only"),
])
def test_outcome_comes_from_what_changed(link, changes, end_reason, turns, expected):
    record = CallRecorder(link.sessions, link.clinic_id, "r", "s")
    record.changes, record.end_reason, record.turns = changes, end_reason, turns
    assert record.outcome() == expected


async def test_a_time_limit_is_the_end_reason(link):
    record = CallRecorder(link.sessions, link.clinic_id, "r", "s")
    record.mark("time_limit")
    await record_call(link, [Reply("नमस्ते")], ["हेलो"], recorder=record)
    call, _, _ = _saved(link, record.call_id)
    assert call.end_reason == "time_limit"


# ---------- recording never breaks a call ----------

class BrokenSessions:
    def __call__(self):
        raise RuntimeError("database down")


async def test_a_database_failure_leaves_the_call_working(link):
    record = CallRecorder(BrokenSessions(), link.clinic_id, "r", "s")
    await record_call(link, *BOOKING_CALL, recorder=record)
    assert record.call_id is None
    # the booking itself (its own database) still went through
    assert len(repo.appointments_on(link.sessions(), link.clinic_id, DAY)) == 1


async def test_a_failing_event_handler_leaves_the_call_working(link, monkeypatch):
    def boom(self, ev):
        raise ValueError("bad event")

    monkeypatch.setattr(CallRecorder, "_on_item", boom)
    monkeypatch.setattr(CallRecorder, "_on_tools", boom)
    record = await record_call(link, *BOOKING_CALL)
    call, _, _ = _saved(link, record.call_id)
    assert call.outcome == "booked"


async def test_finish_writes_once(link):
    record = await record_call(link, [Reply("नमस्ते")], ["हेलो"])
    await record.finish()
    _, events, _ = _saved(link, record.call_id)
    with link.sessions() as s:
        assert s.query(CallTranscript).count() == 1
    assert len(events) == len(record.events)


# ---------- purge ----------

def _call_at(s, clinic_id, started_at, purge_after):
    call = repo.start_call(s, clinic_id, "r", "s", started_at)
    repo.finish_call(
        s, call.id, ended_at=started_at, end_reason="caller_left", outcome="info_only",
        turn_count=1, error_count=0, appointments=[],
        events=[{"t_ms": 0, "kind": "tool", "name": "x", "duration_ms": 1, "ok": True, "detail": ""}],
        transcript=[{"t_ms": 0, "role": "caller", "text": "hi"}], purge_after=purge_after,
    )
    return call.id


def test_purge_deletes_expired_transcripts_and_old_calls_only(db):
    s, clinic_id = db
    now = utc_now()
    fresh = _call_at(s, clinic_id, now - timedelta(days=1), now + timedelta(days=29))
    expired = _call_at(s, clinic_id, now - timedelta(days=31), now - timedelta(days=1))
    ancient = _call_at(s, clinic_id, now - timedelta(days=TRACE_DAYS + 1), now - timedelta(days=TRACE_DAYS - 29))
    old = now - timedelta(days=TRACE_DAYS)

    assert repo.purge_expired(s, now, old) == (2, 1)
    s.expire_all()
    assert s.get(CallTranscript, fresh) is not None
    assert s.get(CallTranscript, expired) is None
    assert s.get(Call, expired) is not None  # the trace outlives the words
    assert s.query(CallEvent).filter_by(call_id=expired).count() == 1
    assert s.get(Call, ancient) is None
    assert s.query(CallEvent).filter_by(call_id=ancient).count() == 0
    assert repo.purge_expired(s, now, old) == (0, 0)


def test_purge_runs_on_a_session_factory(link):
    assert purge(link.sessions) == (0, 0)
