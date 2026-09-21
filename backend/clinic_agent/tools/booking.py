"""find_available_slots and book_appointment, as LiveKit function tools.

Each call runs the matching `clinic_agent.booking` function in a worker
thread (database I/O must not stall the audio loop) and turns a
BookingError into a ToolError, whose message the LLM reads and relays.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, time
from typing import Literal

from livekit.agents import ToolError, function_tool
from sqlalchemy.orm import Session, sessionmaker

from clinic_agent import booking
from clinic_agent.context import clinic_now


@dataclass(frozen=True)
class ClinicLink:
    """Which clinic a call's tools act on, and how to reach its database."""

    clinic_id: int
    timezone: str
    sessions: sessionmaker[Session]


def booking_tools(link: ClinicLink) -> list:
    async def run(fn: Callable, *args):
        def work():
            with link.sessions() as s:
                return fn(s, link.clinic_id, *args)

        try:
            return await asyncio.to_thread(work)
        except booking.BookingError as err:
            raise ToolError(str(err)) from None

    @function_tool
    async def find_available_slots(
        date: str,
        doctor_name: str = "",
        part_of_day: Literal["any", "morning", "afternoon", "evening"] = "any",
    ) -> str:
        """Find free appointment times on one day. Offer the caller only times this returns.

        Args:
            date: The day as YYYY-MM-DD. Work out words like aaj, kal, parson or
                Monday from the current date in CLINIC FACTS.
            doctor_name: A doctor from CLINIC FACTS if the caller named one or
                described one (e.g. the children's doctor); empty for any doctor.
            part_of_day: Only if the caller asked for morning, afternoon or evening.
        """
        return await run(
            booking.find_slots, _date(date), clinic_now(link.timezone),
            doctor_name or None, None if part_of_day == "any" else part_of_day,
        )

    @function_tool
    async def book_appointment(
        doctor_name: str,
        date: str,
        time: str,
        patient_name: str,
        patient_phone: str,
        caller_confirmed: bool,
    ) -> str:
        """Book an appointment. Call only after reading every detail back to the caller.

        Args:
            doctor_name: The doctor, as named in CLINIC FACTS.
            date: The day as YYYY-MM-DD.
            time: Start time as HH:MM (24-hour), one of the free times found.
            patient_name: The patient's name as the caller gave it.
            patient_phone: The caller's 10-digit mobile number.
            caller_confirmed: True only if you read back the doctor, day, time,
                name and number and the caller clearly said yes.
        """
        if not caller_confirmed:
            raise ToolError(
                "Not booked. Read the doctor, day, time, name and number back to the "
                "caller and book only after they say yes."
            )
        return await run(
            booking.book_slot, doctor_name, _date(date), _time(time),
            patient_name, patient_phone, clinic_now(link.timezone),
        )

    return [find_available_slots, book_appointment]


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise ToolError(f"'{value}' is not a date in YYYY-MM-DD form.") from None


def _time(value: str) -> time:
    try:
        return time.fromisoformat(value.strip())
    except ValueError:
        raise ToolError(f"'{value}' is not a time in HH:MM form.") from None
