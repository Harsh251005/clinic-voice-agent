"""Appointment tools for the agent: find slots, book, look up, cancel, move.

Each call runs the matching `clinic_agent.booking` function in a worker
thread (database I/O must not stall the audio loop) and turns a
BookingError into a ToolError, whose message the LLM reads and relays.
While it runs, the caller hears "one moment" unless the model already said
something (tools/speech.py).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, time
from typing import Literal

from livekit.agents import RunContext, ToolError, function_tool

from clinic_agent import booking
from clinic_agent.context import clinic_now
from clinic_agent.store.db import Sessions
from clinic_agent.tools.speech import filler_unless_spoken


@dataclass(frozen=True)
class ClinicLink:
    """Which clinic a call's tools act on, and how to reach its database."""

    clinic_id: int
    timezone: str
    sessions: Sessions


MAX_MISSED_LOOKUPS = 3


@dataclass(frozen=True)
class _Checked:
    """A booking read back to the caller, waiting for their yes."""

    doctor_name: str
    day: date
    start: time
    patient_name: str
    patient_phone: str
    reason: str
    caller_turns: int  # caller messages heard when it was checked


def _caller_turns(ctx: RunContext | None) -> int | None:
    """How many times the caller has spoken this call. None without a
    session: tests that call a tool directly have no caller."""
    if ctx is None:
        return None
    return sum(1 for it in ctx.session.history.items if it.type == "message" and it.role == "user")


def booking_tools(link: ClinicLink) -> list:
    said: set[str] = set()  # replies whose "one moment" was already spoken
    checked: list[_Checked] = []  # the one booking awaiting the caller's yes (a call's tools are its own)
    missed: list[int] = [0]  # lookups this call that matched nobody

    async def run(ctx: RunContext | None, fn: Callable, *args):
        def work():
            with link.sessions() as s:
                return fn(s, link.clinic_id, *args)

        task = asyncio.ensure_future(asyncio.to_thread(work))  # start before the filler wait
        await filler_unless_spoken(ctx, said)
        try:
            return await task
        except booking.BookingError as err:
            raise ToolError(str(err)) from None

    @function_tool
    async def find_available_slots(
        ctx: RunContext,
        date: str,
        doctor_name: str = "",
        part_of_day: Literal["any", "morning", "afternoon", "evening"] = "any",
    ) -> str:
        """Find every free appointment time on one day. Offer the caller only times this returns.

        It lists every free start time one by one, with its Hindi words in
        brackets ("12:30 (साढ़े बारह बजे)"), grouped as morning
        (before 12:00), afternoon (12:00 to before 17:00) and evening (17:00
        on), and which few to suggest first. Suggest those, and answer
        "anything later / in the evening?" from the full list
        without calling again: for a part of the day, offer only the times
        under that label. Call again only for another day or doctor.

        Args:
            date: The day as YYYY-MM-DD. Work out words like aaj, kal, parson or
                Monday from the current date in CLINIC FACTS.
            doctor_name: A doctor from CLINIC FACTS if the caller named one or
                described one (e.g. the children's doctor); empty for any doctor.
            part_of_day: Only if the caller asked for morning (before 12:00),
                afternoon (12:00 to before 17:00) or evening (17:00 on).
        """
        return await run(
            ctx, booking.find_slots, _date(date), clinic_now(link.timezone),
            doctor_name or None, None if part_of_day == "any" else part_of_day,
        )

    @function_tool
    async def check_booking(
        ctx: RunContext,
        doctor_name: str,
        date: str,
        time: str,
        patient_name: str,
        patient_phone: str,
        reason: str = "",
    ) -> str:
        """Check a booking and get the details to read back. Books nothing.

        Call once the caller has picked a time and given the name and number.
        Then read back what it returns and ask if it is correct.

        Args:
            doctor_name: The doctor, as named in CLINIC FACTS.
            date: The day as YYYY-MM-DD.
            time: Start time as HH:MM (24-hour), one of the free times found.
            patient_name: The patient's name as the caller gave it, in Roman
                letters (e.g. "Ravi Kumar"), never Devanagari.
            patient_phone: The caller's 10-digit mobile number.
            reason: Why the patient is coming, for the clinic's staff. Always
                short, plain English in Roman letters, translated from whatever
                the caller said, never Devanagari (e.g. "Blurred vision for 2
                days", "Tooth pain"). Empty if the caller didn't want to say.
        """
        day, start = _date(date), _time(time)
        details = await run(
            ctx, booking.check_slot, doctor_name, day, start,
            patient_name, patient_phone, clinic_now(link.timezone),
        )
        checked[:] = [_Checked(
            doctor_name, day, start, patient_name, patient_phone, reason, _caller_turns(ctx) or 0,
        )]
        return (
            f"Not booked yet. Read this back to the caller in one sentence, the number "
            f"digit by digit, and ask if it is correct: {details}. If they say yes, call "
            f"book_appointment. If anything is wrong, fix it and call check_booking again."
        )

    @function_tool
    async def book_appointment(ctx: RunContext) -> str:
        """Book the appointment check_booking last checked. Call only after the caller heard the read-back and said yes."""
        if not checked:
            raise ToolError(
                "Nothing to book. Call check_booking first, read its details back to the "
                "caller, and book only after they say yes."
            )
        c = checked[0]
        turns = _caller_turns(ctx)
        if turns is not None and turns <= c.caller_turns:
            # Code, not the model's word: the caller must have answered the read-back.
            raise ToolError(
                "Not booked: the caller hasn't answered yet. Read the details from "
                "check_booking back to them, ask if they are correct, and wait for a yes."
            )
        result = await run(
            ctx, booking.book_slot, c.doctor_name, c.day, c.start,
            c.patient_name, c.patient_phone, clinic_now(link.timezone), c.reason,
        )
        checked.clear()
        return result

    @function_tool
    async def find_my_appointments(ctx: RunContext, patient_phone: str, patient_name: str) -> str:
        """List one patient's upcoming appointments. Both the number and the name must match.

        Args:
            patient_phone: The 10-digit mobile number the appointment was booked with.
            patient_name: The patient's name, in Roman letters (e.g. "Ravi").
        """
        # A cap per call, so neither the model nor a caller can try name after
        # name on someone's number (gpt-6-luna guessed one in a live test).
        if missed[0] >= MAX_MISSED_LOOKUPS:
            raise ToolError(
                "No more lookups on this call. Tell the caller you couldn't find the "
                "appointment and that the clinic's staff can help them in person."
            )
        try:
            return await run(
                ctx, booking.find_appointments, patient_phone, patient_name, clinic_now(link.timezone)
            )
        except ToolError:
            missed[0] += 1
            raise

    @function_tool
    async def cancel_appointment(
        ctx: RunContext, appointment_id: int, patient_phone: str, patient_name: str, caller_confirmed: bool
    ) -> str:
        """Cancel one of the caller's appointments. Call only after reading it back.

        Args:
            appointment_id: The appointment number from find_my_appointments.
            patient_phone: The mobile number it was booked with.
            patient_name: The patient's name, in Roman letters, as for find_my_appointments.
            caller_confirmed: True only if you read back the doctor, day and time
                and the caller clearly said yes, cancel it.
        """
        if not caller_confirmed:
            raise ToolError(
                "Not cancelled. Read the doctor, day and time back to the caller and "
                "cancel only after they say yes."
            )
        return await run(
            ctx, booking.cancel_booking, appointment_id, patient_phone, patient_name,
            clinic_now(link.timezone),
        )

    @function_tool
    async def reschedule_appointment(
        ctx: RunContext,
        appointment_id: int,
        patient_phone: str,
        patient_name: str,
        date: str,
        time: str,
        caller_confirmed: bool,
        doctor_name: str = "",
    ) -> str:
        """Move one of the caller's appointments to a new free time. Call only after reading it back.

        Args:
            appointment_id: The appointment number from find_my_appointments.
            patient_phone: The mobile number it was booked with.
            patient_name: The patient's name, in Roman letters, as for find_my_appointments.
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
            ctx, booking.reschedule_booking, appointment_id, patient_phone, patient_name,
            _date(date), _time(time),
            clinic_now(link.timezone), doctor_name or None,
        )

    return [
        find_available_slots, check_booking, book_appointment,
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
