"""The LiveKit wrappers: check-then-book, input parsing, errors reaching the LLM,
and database work running in a worker thread (hence a file database).
Called directly with no session (ctx None), so no "one moment" is spoken and
there is no caller to answer the read-back; tests/test_booking_readback.py
covers that gate and tests/test_call_speech.py the filler, through a real session."""

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
    find, check, book, *_ = booking_tools(ClinicLink(clinic_id, "Asia/Kolkata", sessions))

    async def check_then_book(**details):
        await check(None, **details)
        return await book(None)

    return find, check_then_book, sessions, clinic_id


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
    assert "free start times - evening: 17:00 (पाँच बजे), 17:15 (सवा पाँच बजे)" in found and found.endswith("suggest first 17:00, 17:15, 17:30.")
    booked = await book(
        doctor_name="Asha", date=day, time="17:00",
        patient_name="Ravi", patient_phone="9876543210",
    )
    assert booked.startswith("Booked, appointment number")
    with sessions() as s:
        assert len(repo.appointments_on(s, clinic_id, date.fromisoformat(day))) == 1


async def test_check_reads_back_the_details_and_books_nothing(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/tools.db")
    migrations.upgrade(engine)
    sessions = session_factory(engine)
    with sessions() as s:
        clinic_id = seed_demo(s)
    _, check, book, *_ = booking_tools(ClinicLink(clinic_id, "Asia/Kolkata", sessions))
    day = next_working_day()
    with pytest.raises(ToolError, match="Nothing to book. Call check_booking first"):
        await book(None)
    said = await check(None,
        doctor_name="Asha", date=day.isoformat(), time="17:00",
        patient_name="Ravi", patient_phone="+91 98765 43210",
    )
    assert said.startswith("Not booked yet.")
    assert f"Dr. Asha Mehta, {day:%A %d %B %Y}, 17:00 (पाँच बजे), for Ravi, mobile 9 8 7 6 5 4 3 2 1 0" in said
    with sessions() as s:
        assert repo.appointments_on(s, clinic_id, day) == []


async def test_check_refuses_a_time_that_is_not_free(tools):
    _, check_then_book, *_ = tools
    day = next_working_day().isoformat()
    await check_then_book(doctor_name="Asha", date=day, time="17:00", patient_name="Ravi", patient_phone="9876543210")
    with pytest.raises(ToolError, match="not free at 17:00"):
        await check_then_book(doctor_name="Asha", date=day, time="17:00", patient_name="Sita", patient_phone="9876543211")


async def test_bad_date_and_time_become_tool_errors(tools):
    find, book, *_ = tools
    with pytest.raises(ToolError, match="not a date in YYYY-MM-DD"):
        await find(None, date="kal")
    with pytest.raises(ToolError, match="not a time in HH:MM"):
        await book(
            doctor_name="Asha", date=next_working_day().isoformat(), time="shaam paanch",
            patient_name="Ravi", patient_phone="9876543210",
        )


async def test_booking_errors_reach_the_llm_as_tool_errors(tools):
    find, *_ = tools
    with pytest.raises(ToolError, match="No doctor called 'Dr. Sharma'"):
        await find(None, date=next_working_day().isoformat(), doctor_name="Dr. Sharma")


async def test_find_cancel_through_the_tools(tools):
    find, book, sessions, clinic_id = tools
    day = next_working_day().isoformat()
    await book(
        doctor_name="Asha", date=day, time="17:00",
        patient_name="Ravi", patient_phone="9876543210",
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


async def test_lookups_stop_after_three_misses(tools):
    _, book, sessions, clinic_id = tools
    await book(doctor_name="Asha", date=next_working_day().isoformat(), time="17:00",
               patient_name="Ravi", patient_phone="9876543210")
    mine, _, _ = _manage(sessions, clinic_id)
    for guess in ("Amit", "Sita", "Mohan"):
        with pytest.raises(ToolError, match="No upcoming appointments"):
            await mine(None, patient_phone="9876543210", patient_name=guess)
    # Even the right name is refused now: a guesser can't keep going.
    with pytest.raises(ToolError, match="No more lookups on this call"):
        await mine(None, patient_phone="9876543210", patient_name="Ravi")


def _manage(sessions, clinic_id):
    _, _, _, mine, cancel, move = booking_tools(ClinicLink(clinic_id, "Asia/Kolkata", sessions))
    return mine, cancel, move
