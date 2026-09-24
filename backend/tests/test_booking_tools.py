"""The LiveKit wrappers: confirmation gate, input parsing, errors reaching the LLM,
and database work running in a worker thread (hence a file database).
Called directly with no session (ctx None), so no "one moment" is spoken;
tests/test_call_speech.py covers that through a real session."""

from datetime import date, timedelta

import pytest
from livekit.agents import ToolError

from clinic_agent.context import clinic_now
from clinic_agent.store import repo
from clinic_agent.store import migrations
from clinic_agent.store.db import make_engine, session_factory
from clinic_agent.tools.booking import ClinicLink, booking_tools
from seeds.demo_clinic import seed_demo


@pytest.fixture
def tools(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/tools.db")
    migrations.upgrade(engine)
    sessions = session_factory(engine)
    with sessions() as s:
        clinic_id = seed_demo(s)
    find, book, *_ = booking_tools(ClinicLink(clinic_id, "Asia/Kolkata", sessions))
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
    found = await find(None, date=day, doctor_name="Asha", part_of_day="evening")
    assert "free start times - evening: 17:00, 17:15" in found and found.endswith("suggest first 17:00, 17:15, 17:30.")
    booked = await book(None, 
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
        await book(None, 
            doctor_name="Asha", date=day.isoformat(), time="17:00",
            patient_name="Ravi", patient_phone="9876543210", caller_confirmed=False,
        )
    with sessions() as s:
        assert repo.appointments_on(s, clinic_id, day) == []


async def test_bad_date_and_time_become_tool_errors(tools):
    find, book, *_ = tools
    with pytest.raises(ToolError, match="not a date in YYYY-MM-DD"):
        await find(None, date="kal")
    with pytest.raises(ToolError, match="not a time in HH:MM"):
        await book(None, 
            doctor_name="Asha", date=next_working_day().isoformat(), time="shaam paanch",
            patient_name="Ravi", patient_phone="9876543210", caller_confirmed=True,
        )


async def test_booking_errors_reach_the_llm_as_tool_errors(tools):
    find, *_ = tools
    with pytest.raises(ToolError, match="No doctor called 'Dr. Sharma'"):
        await find(None, date=next_working_day().isoformat(), doctor_name="Dr. Sharma")


async def test_find_cancel_through_the_tools(tools):
    find, book, sessions, clinic_id = tools
    day = next_working_day().isoformat()
    await book(None, 
        doctor_name="Asha", date=day, time="17:00",
        patient_name="Ravi", patient_phone="9876543210", caller_confirmed=True,
    )
    mine, cancel, move = _manage(sessions, clinic_id)
    listed = await mine(None, patient_phone="9876543210", patient_name="Ravi")
    appt_id = int(listed.split(":")[0].removeprefix("Appointment "))
    with pytest.raises(ToolError, match="Not cancelled"):
        await cancel(None, appointment_id=appt_id, patient_phone="9876543210", patient_name="Ravi", caller_confirmed=False)
    with pytest.raises(ToolError, match="Not moved"):
        await move(None, 
            appointment_id=appt_id, patient_phone="9876543210", patient_name="Ravi", date=day, time="17:15",
            caller_confirmed=False,
        )
    moved = await move(None, 
        appointment_id=appt_id, patient_phone="9876543210", patient_name="Ravi", date=day, time="17:15",
        caller_confirmed=True,
    )
    assert moved.startswith(f"Moved appointment {appt_id}")
    cancelled = await cancel(None, appointment_id=appt_id, patient_phone="9876543210", patient_name="Ravi", caller_confirmed=True)
    assert cancelled.startswith(f"Cancelled appointment {appt_id}")


def _manage(sessions, clinic_id):
    _, _, mine, cancel, move = booking_tools(ClinicLink(clinic_id, "Asia/Kolkata", sessions))
    return mine, cancel, move
