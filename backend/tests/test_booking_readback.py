"""The read-back gate, through a real AgentSession with a scripted LLM: a
booking happens only after the caller has spoken since check_booking, so
the model can't book in the same breath as the read-back (seen live on
gpt-6-luna), whatever it believes the caller said."""

from datetime import date, datetime, time

import pytest
from livekit.agents import AgentSession

from clinic_agent.agent import ClinicAgent
from clinic_agent.store import migrations, repo
from clinic_agent.store.db import make_engine, session_factory
from clinic_agent.tools.booking import ClinicLink, booking_tools
from seeds.demo_clinic import seed_demo
from tests.fake_llm import FakeLLM, Reply
from tests.test_booking_tools import next_working_day

DAY = next_working_day()
CHECK = ("check_booking", {
    "doctor_name": "Asha", "date": DAY.isoformat(), "time": "17:00",
    "patient_name": "Ravi", "patient_phone": "9876543210", "reason": "Fever",
})
BOOK = ("book_appointment", {})


@pytest.fixture
def link(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/readback.db")
    migrations.upgrade(engine)
    sessions = session_factory(engine)
    with sessions() as s:
        clinic_id = seed_demo(s)
    return ClinicLink(clinic_id, "Asia/Kolkata", sessions)


async def _silent():
    return None


async def converse(link, replies, turns):
    """Play the caller's turns against scripted replies; returns the fake LLM."""
    fake = FakeLLM(replies)
    agent = ClinicAgent("test", booking_tools(link))
    agent.on_enter = _silent
    async with AgentSession(llm=fake) as session:
        await session.start(agent)
        for text in turns:
            await session.run(user_input=text)
        await session.aclose()
    return fake


def _booked(link, day: date):
    with link.sessions() as s:
        return repo.appointments_on(s, link.clinic_id, day)


def _outputs(fake):
    return [it.output for it in fake.requests[-1].items if it.type == "function_call_output"]


async def test_booking_in_the_same_breath_as_the_read_back_is_refused(link):
    replies = [Reply(calls=[CHECK]), Reply(calls=[BOOK]), Reply("क्या यह सही है?")]
    fake = await converse(link, replies, ["पाँच बजे, नाम रवि, नंबर 9876543210"])
    assert _booked(link, DAY) == []
    assert any("the caller hasn't answered yet" in o for o in _outputs(fake))


async def test_books_after_the_caller_answers_the_read_back(link):
    replies = [
        Reply(calls=[CHECK]), Reply("डॉ. आशा मेहता, पाँच बजे, रवि, सही है?"),
        Reply(calls=[BOOK]), Reply("बुक हो गया।"),
    ]
    await converse(link, replies, ["पाँच बजे, नाम रवि, नंबर 9876543210", "हाँ, सही है"])
    (appt,) = _booked(link, DAY)
    assert appt.patient.name == "Ravi" and appt.reason == "Fever"
    assert appt.starts_at.hour == 17


async def test_book_without_a_check_is_refused(link):
    fake = await converse(link, [Reply(calls=[BOOK]), Reply("...")], ["बुक कर दो"])
    assert _booked(link, DAY) == []
    assert any("Call check_booking first" in o for o in _outputs(fake))


# ---------- cancel and move: confirm by repeating the call ----------

def _booked_for_ravi(link):
    with link.sessions() as s:
        asha = repo.get_clinic(s, link.clinic_id).doctors[0]
        return repo.book(s, link.clinic_id, asha.id, datetime.combine(DAY, time(17)), "Ravi", "9876543210").id


def _cancel(appt_id):
    return ("cancel_appointment", {"appointment_id": appt_id, "patient_phone": "9876543210", "patient_name": "Ravi"})


def _move(appt_id, at="17:30"):
    return ("reschedule_appointment", {"appointment_id": appt_id, "patient_phone": "9876543210",
                                       "patient_name": "Ravi", "date": DAY.isoformat(), "time": at})


def _status(link, appt_id):
    with link.sessions() as s:
        a = repo.get_appointment(s, appt_id)
        return a.status, a.starts_at.strftime("%H:%M")


async def test_cancelling_in_the_same_breath_as_the_read_back_is_refused(link):
    appt = _booked_for_ravi(link)
    fake = await converse(link, [Reply(calls=[_cancel(appt)]), Reply(calls=[_cancel(appt)]), Reply("...")], ["कैंसल कर दो"])
    assert _status(link, appt) == ("booked", "17:00")
    outputs = _outputs(fake)
    assert any(o.startswith("Not cancelled yet") for o in outputs)
    assert any("the caller hasn't answered yet" in o for o in outputs)


async def test_cancels_after_the_caller_says_yes(link):
    appt = _booked_for_ravi(link)
    replies = [Reply(calls=[_cancel(appt)]), Reply("पाँच बजे वाला कैंसल करूँ?"), Reply(calls=[_cancel(appt)]), Reply("हो गया।")]
    await converse(link, replies, ["कैंसल कर दो", "हाँ"])
    assert _status(link, appt)[0] == "cancelled"


async def test_moves_only_what_was_read_back(link):
    appt = _booked_for_ravi(link)
    replies = [
        Reply(calls=[_move(appt, "17:30")]), Reply("साढ़े पाँच बजे, ठीक है?"),
        Reply(calls=[_move(appt, "18:00")]), Reply("छह बजे, ठीक है?"),  # a different time: a new read-back
        Reply(calls=[_move(appt, "18:00")]), Reply("हो गया।"),
    ]
    fake = await converse(link, replies, ["साढ़े पाँच कर दो", "नहीं, छह बजे", "हाँ"])
    assert _status(link, appt) == ("booked", "18:00")
    assert sum(o.startswith("Not moved yet") for o in _outputs(fake)) == 2
