"""The LiveKit wrappers: confirmation gate, input parsing, errors reaching the LLM,
and database work running in a worker thread (hence a file database)."""

from datetime import date, timedelta

import pytest
from livekit.agents import ToolError

from clinic_agent.context import clinic_now
from clinic_agent.store import repo
from clinic_agent.store.db import init_db, make_engine, session_factory
from clinic_agent.tools.booking import ClinicLink, booking_tools
from seeds.demo_clinic import seed_demo


@pytest.fixture
def tools(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/tools.db")
    init_db(engine)
    sessions = session_factory(engine)
    with sessions() as s:
        clinic_id = seed_demo(s)
    find, book = booking_tools(ClinicLink(clinic_id, "Asia/Kolkata", sessions))
    return find, book, sessions, clinic_id


def next_working_day() -> date:
    """A day after today on which Dr. Asha sits (Monday-Saturday)."""
    d = clinic_now("Asia/Kolkata").date() + timedelta(days=1)
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d


async def test_find_then_book_through_the_tools(tools):
    find, book, sessions, clinic_id = tools
    day = next_working_day().isoformat()
    found = await find(date=day, doctor_name="Asha", part_of_day="evening")
    assert found.endswith("17:00, 17:15, 17:30.")
    booked = await book(
        doctor_name="Asha", date=day, time="17:00",
        patient_name="Ravi", patient_phone="9876543210", caller_confirmed=True,
    )
    assert booked.startswith("Booked, appointment number")
    with sessions() as s:
        assert len(repo.appointments_on(s, clinic_id, date.fromisoformat(day))) == 1


async def test_unconfirmed_booking_is_refused_and_nothing_stored(tools):
    _, book, sessions, clinic_id = tools
    day = next_working_day()
    with pytest.raises(ToolError, match="Read the doctor, day, time, name and number back"):
        await book(
            doctor_name="Asha", date=day.isoformat(), time="17:00",
            patient_name="Ravi", patient_phone="9876543210", caller_confirmed=False,
        )
    with sessions() as s:
        assert repo.appointments_on(s, clinic_id, day) == []


async def test_bad_date_and_time_become_tool_errors(tools):
    find, book, *_ = tools
    with pytest.raises(ToolError, match="not a date in YYYY-MM-DD"):
        await find(date="kal")
    with pytest.raises(ToolError, match="not a time in HH:MM"):
        await book(
            doctor_name="Asha", date=next_working_day().isoformat(), time="shaam paanch",
            patient_name="Ravi", patient_phone="9876543210", caller_confirmed=True,
        )


async def test_booking_errors_reach_the_llm_as_tool_errors(tools):
    find, *_ = tools
    with pytest.raises(ToolError, match="No doctor called 'Dr. Sharma'"):
        await find(date=next_working_day().isoformat(), doctor_name="Dr. Sharma")
