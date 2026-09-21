"""Finding and booking slots: the rules behind the agent's booking tools.

Plain functions over a database session - no LiveKit - so every rule is
testable directly. Results and errors are short English sentences written
for the LLM to turn into speech; a BookingError's message tells the caller
what went wrong and, where possible, what to offer instead.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from clinic_agent import scheduling
from clinic_agent.store import repo
from clinic_agent.store.models import Clinic, Doctor, TimeOff


class BookingError(Exception):
    """Something the caller must be told; the message says what and why."""


def normalise_phone(raw: str) -> str:
    """A 10-digit Indian mobile number, accepting +91 / 0 prefixes and spaces."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise BookingError(
            f"'{raw}' is not a valid 10-digit mobile number. Ask the caller to repeat it."
        )
    return digits


def resolve_doctor(clinic: Clinic, name: str) -> Doctor:
    """Match a spoken doctor name to one active doctor, tolerating 'Dr.' and partial names."""
    active = [d for d in clinic.doctors if d.active]
    wanted = _name_key(name)
    exact = [d for d in active if _name_key(d.name) == wanted]
    partial = exact or [d for d in active if wanted and wanted in _name_key(d.name)]
    if len(partial) == 1:
        return partial[0]
    names = ", ".join(d.name for d in active) or "none"
    if not partial:
        raise BookingError(f"No doctor called '{name}' at this clinic. Doctors: {names}.")
    raise BookingError(f"'{name}' matches more than one doctor: {names}. Ask which one.")


def find_slots(
    s: Session,
    clinic_id: int,
    day: date,
    now: datetime,
    doctor_name: str | None = None,
    part_of_day: str | None = None,
) -> str:
    clinic = repo.get_clinic(s, clinic_id)
    _check_day(day, now, clinic)
    doctors = [resolve_doctor(clinic, doctor_name)] if doctor_name else [d for d in clinic.doctors if d.active]
    if not doctors:
        raise BookingError("This clinic has no doctors taking appointments.")
    last_day = now.date() + timedelta(days=clinic.booking_window_days)
    time_off = repo.time_off_overlapping(s, clinic.id, day, last_day)

    lines = []
    for doctor in doctors:
        slots = _day_slots(s, doctor, day, time_off, now, part_of_day)
        if slots:
            lines.append(f"{doctor.name} on {_day(day)}: {_times(slots[: clinic.slots_offered])}.")
            continue
        why = _why_none(doctor, day, time_off, part_of_day)
        nxt = _next_free(s, doctor, day, last_day, time_off, now, part_of_day)
        tail = (
            f" Next free: {_day(nxt[0].date())}, {_times(nxt[: clinic.slots_offered])}."
            if nxt else f" Nothing free up to {_day(last_day)}."
        )
        lines.append(f"{doctor.name} on {_day(day)}: none - {why}.{tail}")
    return " ".join(lines)


def book_slot(
    s: Session,
    clinic_id: int,
    doctor_name: str,
    day: date,
    start: time,
    patient_name: str,
    patient_phone: str,
    now: datetime,
) -> str:
    if not patient_name.strip():
        raise BookingError("The caller's name is missing. Ask for it.")
    phone = normalise_phone(patient_phone)
    clinic = repo.get_clinic(s, clinic_id)
    doctor = resolve_doctor(clinic, doctor_name)
    _check_day(day, now, clinic)

    starts_at = datetime.combine(day, start)
    time_off = repo.time_off_overlapping(s, clinic.id, day, day)
    free = _day_slots(s, doctor, day, time_off, now, None)
    if starts_at not in free:
        offer = f" Free times that day: {_times(free[: clinic.slots_offered])}." if free else ""
        raise BookingError(f"{doctor.name} is not free at {start:%H:%M} on {_day(day)}.{offer}")

    try:
        appt = repo.book(s, clinic.id, doctor.id, starts_at, patient_name.strip(), phone, source="voice")
    except repo.SlotTaken:
        free = _day_slots(s, doctor, day, time_off, now, None)
        offer = f" Offer: {_times(free[: clinic.slots_offered])}." if free else ""
        raise BookingError(f"That time was just taken by another caller.{offer}") from None
    return (
        f"Booked, appointment number {appt.id}: {doctor.name}, {_day(day)} at {start:%H:%M}, "
        f"for {appt.patient.name}, mobile {phone}."
    )


# ---------- helpers ----------

def _check_day(day: date, now: datetime, clinic: Clinic) -> None:
    try:
        scheduling.check_bookable_day(day, now.date(), clinic.booking_window_days)
    except scheduling.NotBookable as err:
        raise BookingError(f"Can't book that day: {err}.") from None


def _off_pairs(time_off: list[TimeOff]):
    return [(t.doctor_id, t.date_from, t.date_to) for t in time_off]


def _day_slots(s, doctor: Doctor, day: date, time_off, now, part_of_day) -> list[datetime]:
    if scheduling.is_off(day, doctor.id, _off_pairs(time_off)):
        return []
    sittings = [(h.start, h.end) for h in doctor.hours if h.weekday == day.weekday()]
    if not sittings:
        return []
    return scheduling.free_slots(
        day, sittings, doctor.slot_minutes, repo.booked_intervals(s, doctor.id, day),
        now, part_of_day=part_of_day,
    )


def _why_none(doctor: Doctor, day: date, time_off: list[TimeOff], part_of_day) -> str:
    for t in time_off:
        if t.date_from <= day <= t.date_to:
            if t.doctor_id is None:
                return f"clinic closed{f' ({t.reason})' if t.reason else ''}"
            if t.doctor_id == doctor.id:
                return "doctor on leave"
    if not any(h.weekday == day.weekday() for h in doctor.hours):
        return f"doctor does not sit on {day:%A}s"
    return f"fully booked{f' in the {part_of_day}' if part_of_day else ''}"


def _next_free(s, doctor, day, last_day, time_off, now, part_of_day) -> list[datetime]:
    d = day + timedelta(days=1)
    while d <= last_day:
        if slots := _day_slots(s, doctor, d, time_off, now, part_of_day):
            return slots
        d += timedelta(days=1)
    return []


def _day(d: date) -> str:
    return d.strftime("%A %d %B %Y")


def _times(slots: list[datetime]) -> str:
    return ", ".join(f"{t:%H:%M}" for t in slots)


def _name_key(name: str) -> str:
    return re.sub(r"^(dr|doctor)\.?\s+", "", name.strip().lower()).replace(".", "")
