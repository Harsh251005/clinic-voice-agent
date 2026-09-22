"""Appointment tools for the agent: find slots, book, look up, cancel, move.

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

from clinic_agent import booking
from clinic_agent.context import clinic_now
from clinic_agent.store.db import Sessions


@dataclass(frozen=True)
class ClinicLink:
    """Which clinic a call's tools act on, and how to reach its database."""

    clinic_id: int
    timezone: str
    sessions: Sessions


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
        """Find every free appointment time on one day. Offer the caller only times this returns.

        It lists all free start times as ranges ("10:00 to 12:45, every 15
        minutes") and which few to suggest first. Suggest those, and answer
        "anything later / after eleven / in the evening?" from the full list
        without calling again. Call again only for another day or doctor.

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

    @function_tool
    async def find_my_appointments(patient_phone: str) -> str:
        """List the caller's upcoming appointments, found by the mobile number they booked with.

        Args:
            patient_phone: The 10-digit mobile number the appointment was booked with.
        """
        return await run(booking.find_appointments, patient_phone, clinic_now(link.timezone))

    @function_tool
    async def cancel_appointment(appointment_id: int, patient_phone: str, caller_confirmed: bool) -> str:
        """Cancel one of the caller's appointments. Call only after reading it back.

        Args:
            appointment_id: The appointment number from find_my_appointments.
            patient_phone: The mobile number it was booked with.
            caller_confirmed: True only if you read back the doctor, day and time
                and the caller clearly said yes, cancel it.
        """
        if not caller_confirmed:
            raise ToolError(
                "Not cancelled. Read the doctor, day and time back to the caller and "
                "cancel only after they say yes."
            )
        return await run(
            booking.cancel_booking, appointment_id, patient_phone, clinic_now(link.timezone)
        )

    @function_tool
    async def reschedule_appointment(
        appointment_id: int,
        patient_phone: str,
        date: str,
        time: str,
        caller_confirmed: bool,
        doctor_name: str = "",
    ) -> str:
        """Move one of the caller's appointments to a new free time. Call only after reading it back.

        Args:
            appointment_id: The appointment number from find_my_appointments.
            patient_phone: The mobile number it was booked with.
            date: The new day as YYYY-MM-DD.
            time: The new start time as HH:MM (24-hour), one of the free times found.
            caller_confirmed: True only if you read back the old and new day and
                time and the caller clearly said yes.
            doctor_name: Only if the caller wants a different doctor; empty keeps the same one.
        """
        if not caller_confirmed:
            raise ToolError(
                "Not moved. Read the old and the new day and time back to the caller and "
                "move it only after they say yes."
            )
        return await run(
            booking.reschedule_booking, appointment_id, patient_phone, _date(date), _time(time),
            clinic_now(link.timezone), doctor_name or None,
        )

    return [
        find_available_slots, book_appointment,
        find_my_appointments, cancel_appointment, reschedule_appointment,
    ]


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
