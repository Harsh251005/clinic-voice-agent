"""Every query the agent and dashboard make. Writes commit before returning.

Callers get model objects back and our own exceptions on failure, never a
SQLAlchemy error - nothing outside `store/` should need to import it.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from clinic_agent.store.models import (
    Appointment,
    Clinic,
    ClinicFaq,
    Doctor,
    DoctorHours,
    Patient,
    TimeOff,
)


class NotFound(LookupError):
    pass


class SlotTaken(Exception):
    """The doctor already has a booking at that time."""


# ---------- clinics ----------

def get_clinic(s: Session, clinic_id: int) -> Clinic:
    """The clinic with its doctors, their hours and the FAQ, loaded eagerly."""
    clinic = s.scalar(
        select(Clinic)
        .where(Clinic.id == clinic_id)
        .options(
            selectinload(Clinic.doctors).selectinload(Doctor.hours),
            selectinload(Clinic.faq),
        )
    )
    if clinic is None:
        raise NotFound(f"no clinic with id {clinic_id}")
    return clinic


def get_clinic_by_slug(s: Session, slug: str) -> Clinic:
    """The clinic a call link is for, loaded like get_clinic."""
    clinic_id = s.scalar(select(Clinic.id).where(Clinic.slug == slug))
    if clinic_id is None:
        raise NotFound(f"no clinic with link {slug!r}")
    return get_clinic(s, clinic_id)


def list_clinics(s: Session) -> list[Clinic]:
    return list(s.scalars(select(Clinic).order_by(Clinic.id)))


def create_clinic(s: Session, **fields) -> Clinic:
    """A new clinic. Its call-link slug is made from the name unless given."""
    if "slug" in fields:
        _check_slug(s, fields["slug"])
    else:
        fields["slug"] = _free_slug(s, slugify(fields.get("name", "")))
    clinic = Clinic(**fields)
    s.add(clinic)
    s.commit()
    return clinic


SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def slugify(name: str) -> str:
    """"Sharma Skin Clinic" -> "sharma-skin-clinic". Accents are folded; a name
    with no Latin letters or digits (all Devanagari, say) gives "clinic"."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:60].strip("-")
    return slug if len(slug) >= 3 else "clinic"


def set_slug(s: Session, clinic_id: int, slug: str) -> Clinic:
    """Change a clinic's call link. The old link stops working.
    Raises ValueError with a message staff can read."""
    clinic = _get(s, Clinic, clinic_id)
    if slug != clinic.slug:
        _check_slug(s, slug)
        clinic.slug = slug
        s.commit()
    return clinic


def _check_slug(s: Session, slug: str) -> None:
    if not (3 <= len(slug) <= 60 and SLUG.fullmatch(slug)):
        raise ValueError(
            "The link name must be 3-60 characters: lowercase letters, digits and "
            "single hyphens, e.g. sharma-skin."
        )
    if s.scalar(select(Clinic.id).where(Clinic.slug == slug)) is not None:
        raise ValueError(f"The link name {slug!r} is already taken by another clinic.")


def _free_slug(s: Session, base: str) -> str:
    taken = set(s.scalars(select(Clinic.slug).where(Clinic.slug.like(f"{base}%"))))
    slug, n = base, 2
    while slug in taken:
        slug = f"{base[:56]}-{n}"
        n += 1
    return slug


def update_clinic(s: Session, clinic_id: int, **fields) -> Clinic:
    """Details and booking rules. The slug changes only through set_slug."""
    if "slug" in fields:
        raise TypeError("use set_slug to change a clinic's call link")
    clinic = _get(s, Clinic, clinic_id)
    for key, value in fields.items():
        setattr(clinic, key, value)
    s.commit()
    return clinic


# ---------- FAQ ----------

def add_faq(s: Session, clinic_id: int, question: str, answer: str) -> ClinicFaq:
    faq = ClinicFaq(clinic_id=clinic_id, question=question, answer=answer)
    s.add(faq)
    s.commit()
    return faq


def delete_faq(s: Session, faq_id: int) -> None:
    s.delete(_get(s, ClinicFaq, faq_id))
    s.commit()


# ---------- doctors ----------

def add_doctor(s: Session, clinic_id: int, **fields) -> Doctor:
    doctor = Doctor(clinic_id=clinic_id, **fields)
    s.add(doctor)
    s.commit()
    return doctor


def update_doctor(s: Session, doctor_id: int, **fields) -> Doctor:
    doctor = _get(s, Doctor, doctor_id)
    for key, value in fields.items():
        setattr(doctor, key, value)
    s.commit()
    return doctor


def delete_doctor(s: Session, doctor_id: int) -> None:
    s.delete(_get(s, Doctor, doctor_id))
    s.commit()


def set_doctor_hours(
    s: Session, doctor_id: int, sittings: Iterable[tuple[int, time, time]]
) -> None:
    """Replace the doctor's whole weekly schedule with (weekday, start, end) rows."""
    doctor = _get(s, Doctor, doctor_id)
    sittings = list(sittings)
    for weekday, start, end in sittings:
        if not 0 <= weekday <= 6:
            raise ValueError(f"weekday must be 0-6, got {weekday}")
        if start >= end:
            raise ValueError(f"sitting must end after it starts: {start}-{end}")
    doctor.hours = [DoctorHours(weekday=w, start=a, end=b) for w, a, b in sittings]
    s.commit()


# ---------- time off ----------

def add_time_off(
    s: Session,
    clinic_id: int,
    date_from: date,
    date_to: date,
    doctor_id: int | None = None,
    reason: str = "",
) -> TimeOff:
    if date_to < date_from:
        raise ValueError("time off must end on or after the day it starts")
    off = TimeOff(
        clinic_id=clinic_id, doctor_id=doctor_id,
        date_from=date_from, date_to=date_to, reason=reason,
    )
    s.add(off)
    s.commit()
    return off


def delete_time_off(s: Session, time_off_id: int) -> None:
    s.delete(_get(s, TimeOff, time_off_id))
    s.commit()


def time_off_overlapping(
    s: Session, clinic_id: int, day_from: date, day_to: date
) -> list[TimeOff]:
    return list(s.scalars(
        select(TimeOff)
        .where(
            TimeOff.clinic_id == clinic_id,
            TimeOff.date_from <= day_to,
            TimeOff.date_to >= day_from,
        )
        .order_by(TimeOff.date_from)
    ))


# ---------- appointments ----------

def booked_intervals(s: Session, doctor_id: int, day: date) -> list[tuple[datetime, datetime]]:
    """(start, end) of the doctor's booked appointments on this day."""
    start = datetime.combine(day, time.min)
    rows = s.execute(
        select(Appointment.starts_at, Appointment.ends_at).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "booked",
            Appointment.starts_at >= start,
            Appointment.starts_at < start + timedelta(days=1),
        )
    )
    return [(a, b) for a, b in rows]


def appointments_on(
    s: Session, clinic_id: int, day: date, include_cancelled: bool = False
) -> list[Appointment]:
    start = datetime.combine(day, time.min)
    query = (
        select(Appointment)
        .where(
            Appointment.clinic_id == clinic_id,
            Appointment.starts_at >= start,
            Appointment.starts_at < start + timedelta(days=1),
        )
        .options(selectinload(Appointment.doctor), selectinload(Appointment.patient))
        .order_by(Appointment.starts_at, Appointment.doctor_id)
    )
    if not include_cancelled:
        query = query.where(Appointment.status == "booked")
    return list(s.scalars(query))


def book(
    s: Session,
    clinic_id: int,
    doctor_id: int,
    starts_at: datetime,
    patient_name: str,
    patient_phone: str,
    source: str = "voice",
) -> Appointment:
    """Book a slot. Raises SlotTaken if the doctor is already booked then."""
    doctor = _get(s, Doctor, doctor_id)
    if doctor.clinic_id != clinic_id:
        raise NotFound(f"doctor {doctor_id} is not at clinic {clinic_id}")

    patient = _patient(s, clinic_id, patient_name, patient_phone)
    appt = Appointment(
        clinic_id=clinic_id,
        doctor_id=doctor_id,
        patient=patient,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=doctor.slot_minutes),
        source=source,
    )
    s.add(appt)
    try:
        s.commit()
    except IntegrityError as err:
        s.rollback()
        if _is_slot_clash(err):
            raise SlotTaken(f"doctor {doctor_id} is already booked at {starts_at}") from None
        raise
    return appt


def upcoming_for_phone(
    s: Session, clinic_id: int, phone: str, now: datetime
) -> list[Appointment]:
    """Booked appointments from now on for the patient with this phone number."""
    return list(s.scalars(
        select(Appointment)
        .join(Patient, Appointment.patient_id == Patient.id)
        .where(
            Appointment.clinic_id == clinic_id,
            Patient.phone == phone,
            Appointment.status == "booked",
            Appointment.starts_at >= now,
        )
        .options(selectinload(Appointment.doctor), selectinload(Appointment.patient))
        .order_by(Appointment.starts_at)
    ))


def get_appointment(s: Session, appointment_id: int) -> Appointment:
    return _get(s, Appointment, appointment_id)


def move_appointment(
    s: Session, appointment_id: int, doctor_id: int, starts_at: datetime
) -> Appointment:
    """Move a booking to a new doctor/time in one update: it keeps its id, and
    the partial unique index still refuses a slot someone else holds."""
    appt = _get(s, Appointment, appointment_id)
    doctor = _get(s, Doctor, doctor_id)
    if doctor.clinic_id != appt.clinic_id:
        raise NotFound(f"doctor {doctor_id} is not at clinic {appt.clinic_id}")
    appt.doctor_id = doctor.id
    appt.starts_at = starts_at
    appt.ends_at = starts_at + timedelta(minutes=doctor.slot_minutes)
    try:
        s.commit()
    except IntegrityError as err:
        s.rollback()
        if _is_slot_clash(err):
            raise SlotTaken(f"doctor {doctor_id} is already booked at {starts_at}") from None
        raise
    s.refresh(appt)
    return appt


def cancel_appointment(s: Session, appointment_id: int) -> Appointment:
    appt = _get(s, Appointment, appointment_id)
    appt.status = "cancelled"
    s.commit()
    return appt


# ---------- helpers ----------

def _patient(s: Session, clinic_id: int, name: str, phone: str) -> Patient:
    """The patient with this phone and name (case-insensitive), or a new one.

    Never renames: a second name on the same phone is a second person, not a
    correction, so existing appointments keep the name they were booked under.
    """
    patient = s.scalar(
        select(Patient).where(
            Patient.clinic_id == clinic_id,
            Patient.phone == phone,
            func.lower(Patient.name) == name.strip().lower(),
        )
    )
    if patient is None:
        patient = Patient(clinic_id=clinic_id, name=name.strip(), phone=phone)
        s.add(patient)
    return patient


def _is_slot_clash(err: IntegrityError) -> bool:
    """Whether the violation is the one-booking-per-slot index, and not some
    other constraint that must not be reported to a caller as 'slot taken'."""
    text = str(err.orig)
    return "uq_doctor_slot_booked" in text or "appointments.doctor_id, appointments.starts_at" in text


def _get(s: Session, model, row_id: int):
    row = s.get(model, row_id)
    if row is None:
        raise NotFound(f"no {model.__name__} with id {row_id}")
    return row
