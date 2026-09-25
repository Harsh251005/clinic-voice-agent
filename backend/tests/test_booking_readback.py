"""The read-back gate, through a real AgentSession with a scripted LLM: a
booking happens only after the caller has spoken since check_booking, so
the model can't book in the same breath as the read-back (seen live on
gpt-6-luna), whatever it believes the caller said."""

from datetime import date

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
