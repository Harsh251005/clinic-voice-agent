"""Finding and booking slots: the rules behind the agent's booking tools.

Plain functions over a database session - no LiveKit - so every rule is
testable directly. Results and errors are short English sentences written
for the LLM to turn into speech; a BookingError's message tells the caller
what went wrong and, where possible, what to offer instead.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from clinic_agent import scheduling
from clinic_agent.store import repo
from clinic_agent.store.db import Session
from clinic_agent.store.models import Appointment, Clinic, Doctor, TimeOff


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
            lines.append(f"{doctor.name} on {_day(day)}: {_free(slots, doctor, clinic)}.")
            continue
        why = _why_none(doctor, day, time_off, now, part_of_day)
        nxt = _next_free(s, doctor, day, last_day, time_off, now, part_of_day)
        tail = (
            f" Next free day: {_day(nxt[0].date())}, {_free(nxt, doctor, clinic)}."
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
    reason: str = "",
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
        offer = f" That day: {_free(free, doctor, clinic)}." if free else ""
        raise BookingError(f"{doctor.name} is not free at {start:%H:%M} on {_day(day)}.{offer}")

    try:
        appt = repo.book(
            s, clinic.id, doctor.id, starts_at, patient_name.strip(), phone,
            source="voice", reason=_reason(reason),
        )
    except repo.SlotTaken:
        free = _day_slots(s, doctor, day, time_off, now, None)
        offer = f" That day: {_free(free, doctor, clinic)}." if free else ""
        raise BookingError(f"That time was just taken by another caller.{offer}") from None
    return (
        f"Booked, appointment number {appt.id}: {doctor.name}, {_day(day)} at {start:%H:%M}, "
        f"for {appt.patient.name}, mobile {phone}."
    )


def find_appointments(s: Session, clinic_id: int, patient_phone: str, now: datetime) -> str:
    phone = normalise_phone(patient_phone)
    appts = repo.upcoming_for_phone(s, clinic_id, phone, now)
    if not appts:
        raise BookingError(
            f"No upcoming appointments booked with mobile {phone}. Check the number with the caller."
        )
    time_off = repo.time_off_overlapping(s, clinic_id, now.date(), appts[-1].starts_at.date())
    lines = []
    for a in appts:
        line = (
            f"Appointment {a.id}: {a.doctor.name}, {_day(a.starts_at.date())} at {a.starts_at:%H:%M}, "
            f"for {a.patient.name}{f' ({a.reason})' if a.reason else ''}."
        )
        if problem := appointment_problem(a, time_off):
            line += f" Problem: {problem}. Tell the caller and offer to move or cancel it."
        lines.append(line)
    return " ".join(lines)


def appointment_problem(appt: Appointment, time_off: list[TimeOff]) -> str | None:
    """Why a booked appointment can't go ahead as booked, or None.

    Bookings stay booked when staff later add leave, change hours or
    deactivate a doctor; this is how the caller and the dashboard find out.
    """
    doctor, day = appt.doctor, appt.starts_at.date()
    for t in time_off:
        if t.date_from <= day <= t.date_to:
            if t.doctor_id is None:
                return f"the clinic is closed that day{f' ({t.reason})' if t.reason else ''}"
            if t.doctor_id == doctor.id:
                return f"{doctor.name} is on leave that day"
    if not doctor.active:
        return f"{doctor.name} is no longer taking appointments"
    if appt.source == "dashboard":
        return None  # staff may book outside hours on purpose
    if not any(
        h.weekday == day.weekday()
        and datetime.combine(day, h.start) <= appt.starts_at
        and appt.ends_at <= datetime.combine(day, h.end)
        for h in doctor.hours
    ):
        return f"{doctor.name} no longer sits at that time"
    return None


def cancel_booking(
    s: Session, clinic_id: int, appointment_id: int, patient_phone: str, now: datetime
) -> str:
    appt = _owned(s, clinic_id, appointment_id, patient_phone, now)
    repo.cancel_appointment(s, appt.id)
    return (
        f"Cancelled appointment {appt.id}: {appt.doctor.name}, "
        f"{_day(appt.starts_at.date())} at {appt.starts_at:%H:%M}."
    )


def reschedule_booking(
    s: Session,
    clinic_id: int,
    appointment_id: int,
    patient_phone: str,
    day: date,
    start: time,
    now: datetime,
    doctor_name: str | None = None,
) -> str:
    appt = _owned(s, clinic_id, appointment_id, patient_phone, now)
    clinic = repo.get_clinic(s, clinic_id)
    doctor = resolve_doctor(clinic, doctor_name) if doctor_name else appt.doctor
    if not doctor.active:  # resolve_doctor only finds active ones; the booked doctor may not be
        names = ", ".join(d.name for d in clinic.doctors if d.active) or "none"
        raise BookingError(
            f"{doctor.name} is no longer taking appointments. Offer another doctor: {names}."
        )
    _check_day(day, now, clinic)

    old = f"{appt.doctor.name}, {_day(appt.starts_at.date())} at {appt.starts_at:%H:%M}"
    starts_at = datetime.combine(day, start)
    if doctor.id == appt.doctor_id and starts_at == appt.starts_at:
        raise BookingError(f"Appointment {appt.id} is already at that time.")

    time_off = repo.time_off_overlapping(s, clinic.id, day, day)
    free = _day_slots(s, doctor, day, time_off, now, None)
    if starts_at not in free:
        offer = f" That day: {_free(free, doctor, clinic)}." if free else ""
        raise BookingError(f"{doctor.name} is not free at {start:%H:%M} on {_day(day)}.{offer}")

    try:
        repo.move_appointment(s, appt.id, doctor.id, starts_at)
    except repo.SlotTaken:
        raise BookingError(
            "That time was just taken by another caller. The appointment is unchanged."
        ) from None
    return (
        f"Moved appointment {appt.id} from {old} to {doctor.name}, "
        f"{_day(day)} at {start:%H:%M}."
    )


# ---------- staff (dashboard) ----------
#
# Staff have the final say: they may book or move to any time, including
# outside hours, on leave or off the slot grid (a walk-in squeezed in at
# 10:05). The one thing refused is overlapping another booking of the same
# doctor, which would be a real double booking. Messages are for staff.

def free_times(s: Session, clinic_id: int, doctor_id: int, day: date, now: datetime) -> list[datetime]:
    """The doctor's free slots that day by the usual rules (hours, leave,
    bookings), as quick picks for staff. No lead time: a walk-in can be
    booked for right now."""
    doctor = repo.in_clinic(s, Doctor, doctor_id, clinic_id)
    time_off = repo.time_off_overlapping(s, clinic_id, day, day)
    return _day_slots(s, doctor, day, time_off, now, None, lead_minutes=0)


def staff_book(
    s: Session, clinic_id: int, doctor_id: int, starts_at: datetime,
    patient_name: str, patient_phone: str, reason: str = "",
) -> Appointment:
    doctor = repo.in_clinic(s, Doctor, doctor_id, clinic_id)
    name, phone = _staff_patient(patient_name, patient_phone)
    _refuse_overlap(s, doctor, starts_at)
    try:
        return repo.book(s, clinic_id, doctor.id, starts_at, name, phone, source="dashboard", reason=_reason(reason))
    except repo.SlotTaken:
        raise BookingError(f"{doctor.name} is already booked at {starts_at:%H:%M} that day.") from None


def staff_change(
    s: Session, clinic_id: int, appointment_id: int, *,
    doctor_id: int, starts_at: datetime, patient_name: str, patient_phone: str, reason: str,
) -> Appointment:
    """Everything about a booking at once, as the edit form sends it: who,
    why, and (for a booking still on) which doctor and when."""
    appt = repo.in_clinic(s, Appointment, appointment_id, clinic_id)
    doctor = repo.in_clinic(s, Doctor, doctor_id, clinic_id)
    name, phone = _staff_patient(patient_name, patient_phone)
    if (doctor.id, starts_at) != (appt.doctor_id, appt.starts_at):
        if appt.status != "booked":
            raise BookingError("This appointment is cancelled. Book a new one instead of moving it.")
        _refuse_overlap(s, doctor, starts_at, exclude_id=appt.id)
        try:
            repo.move_appointment(s, appt.id, doctor.id, starts_at)
        except repo.SlotTaken:
            raise BookingError(f"{doctor.name} is already booked at {starts_at:%H:%M} that day.") from None
    return repo.update_appointment_details(s, appt.id, name, phone, _reason(reason))


def _staff_patient(name: str, phone: str) -> tuple[str, str]:
    if not name.strip():
        raise BookingError("Enter the patient's name.")
    try:
        return name.strip(), normalise_phone(phone)
    except BookingError:
        raise BookingError(f"'{phone}' isn't a 10-digit Indian mobile number.") from None


def _refuse_overlap(s: Session, doctor: Doctor, starts_at: datetime, exclude_id: int | None = None) -> None:
    ends_at = starts_at + timedelta(minutes=doctor.slot_minutes)
    if clash := repo.overlapping(s, doctor.id, starts_at, ends_at, exclude_id):
        a = clash[0]
        raise BookingError(
            f"{doctor.name} already has {a.patient.name} from {a.starts_at:%H:%M} to {a.ends_at:%H:%M}. "
            "Pick a time that doesn't overlap, or move that booking first."
        )


# ---------- helpers ----------

REASON_MAX = 300


def _reason(text: str) -> str:
    """One line, trimmed to fit the column."""
    return " ".join(text.split())[:REASON_MAX]


def _owned(s: Session, clinic_id: int, appointment_id: int, patient_phone: str, now: datetime):
    """The caller's own upcoming booking, or a BookingError.

    The same message covers 'no such appointment', 'another clinic's' and
    'someone else's', so a guessed id reveals nothing about other patients.
    """
    phone = normalise_phone(patient_phone)
    try:
        appt = repo.get_appointment(s, appointment_id)
    except repo.NotFound:
        appt = None
    if appt is None or appt.clinic_id != clinic_id or appt.patient.phone != phone:
        raise BookingError(
            f"No appointment {appointment_id} booked with mobile {phone}. "
            "Use find_my_appointments to see the caller's bookings."
        )
    if appt.status != "booked":
        raise BookingError(f"Appointment {appointment_id} is already cancelled.")
    if appt.starts_at < now:
        raise BookingError(f"Appointment {appointment_id} has already passed.")
    return appt


def _check_day(day: date, now: datetime, clinic: Clinic) -> None:
    try:
        scheduling.check_bookable_day(day, now.date(), clinic.booking_window_days)
    except scheduling.NotBookable as err:
        raise BookingError(f"Can't book that day: {err}.") from None


def _off_pairs(time_off: list[TimeOff]):
    return [(t.doctor_id, t.date_from, t.date_to) for t in time_off]


def _day_slots(s, doctor: Doctor, day: date, time_off, now, part_of_day, lead_minutes: int = 30) -> list[datetime]:
    if scheduling.is_off(day, doctor.id, _off_pairs(time_off)):
        return []
    sittings = [(h.start, h.end) for h in doctor.hours if h.weekday == day.weekday()]
    if not sittings:
        return []
    return scheduling.free_slots(
        day, sittings, doctor.slot_minutes, repo.booked_intervals(s, doctor.id, day),
        now, lead_minutes=lead_minutes, part_of_day=part_of_day,
    )


def _why_none(doctor: Doctor, day: date, time_off: list[TimeOff], now: datetime, part_of_day) -> str:
    for t in time_off:
        if t.date_from <= day <= t.date_to:
            if t.doctor_id is None:
                return f"clinic closed{f' ({t.reason})' if t.reason else ''}"
            if t.doctor_id == doctor.id:
                return "doctor on leave"
    sittings = [(h.start, h.end) for h in doctor.hours if h.weekday == day.weekday()]
    if not sittings:
        return f"doctor does not sit on {day:%A}s"
    # "Fully booked" only if bookings are the reason, not the clock or the part of day.
    def unbooked(at: datetime) -> list[datetime]:
        return scheduling.free_slots(day, sittings, doctor.slot_minutes, [], at, part_of_day=part_of_day)
    if not unbooked(datetime.combine(day, time.min) - timedelta(days=1)):
        return f"doctor does not sit in the {part_of_day} on {day:%A}s"
    if not unbooked(now):
        return f"no {f'{part_of_day} ' if part_of_day else ''}times left today"
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


def _free(slots: list[datetime], doctor: Doctor, clinic: Clinic) -> str:
    """Every free start time, as runs, plus the few to suggest first.

    The whole day goes to the LLM, not just the first few times, so "anything
    after eleven?" or "evening?" is answered from what is really free rather
    than from a sample. Runs keep it short: a free morning is one range.
    """
    step = timedelta(minutes=doctor.slot_minutes)
    runs: list[list[datetime]] = []
    for t in slots:
        if runs and t - runs[-1][-1] == step:
            runs[-1].append(t)
        else:
            runs.append([t])
    parts = [f"{r[0]:%H:%M}" if len(r) == 1 else f"{r[0]:%H:%M} to {r[-1]:%H:%M}" for r in runs]
    every = f", every {doctor.slot_minutes} minutes" if any(len(r) > 1 for r in runs) else ""
    return (
        f"free start times {', '.join(parts)}{every} ({len(slots)} in all); "
        f"suggest first {_times(slots[: clinic.slots_offered])}"
    )


def _name_key(name: str) -> str:
    return re.sub(r"^(dr|doctor)\.?\s+", "", name.strip().lower()).replace(".", "")
