"""Every query the agent and dashboard make. Writes commit before returning.

Callers get model objects back and our own exceptions on failure, never a
SQLAlchemy error - nothing outside `store/` should need to import it.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
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


def list_clinics(s: Session) -> list[Clinic]:
    return list(s.scalars(select(Clinic).order_by(Clinic.id)))


def create_clinic(s: Session, **fields) -> Clinic:
    clinic = Clinic(**fields)
    s.add(clinic)
    s.commit()
    return clinic


def update_clinic(s: Session, clinic_id: int, **fields) -> Clinic:
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

def booked_starts(s: Session, doctor_id: int, day: date) -> set[datetime]:
    """Start times already taken for this doctor on this day."""
    start = datetime.combine(day, time.min)
    return set(s.scalars(
        select(Appointment.starts_at).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "booked",
            Appointment.starts_at >= start,
            Appointment.starts_at < start + timedelta(days=1),
        )
    ))


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
    except IntegrityError:
        s.rollback()
        raise SlotTaken(f"doctor {doctor_id} is already booked at {starts_at}") from None
    return appt


def cancel_appointment(s: Session, appointment_id: int) -> Appointment:
    appt = _get(s, Appointment, appointment_id)
    appt.status = "cancelled"
    s.commit()
    return appt


# ---------- helpers ----------

def _patient(s: Session, clinic_id: int, name: str, phone: str) -> Patient:
    """One patient per phone number per clinic; the latest name given wins."""
    patient = s.scalar(
        select(Patient).where(Patient.clinic_id == clinic_id, Patient.phone == phone)
    )
    if patient is None:
        patient = Patient(clinic_id=clinic_id, name=name, phone=phone)
        s.add(patient)
    else:
        patient.name = name
    return patient


def _get(s: Session, model, row_id: int):
    row = s.get(model, row_id)
    if row is None:
        raise NotFound(f"no {model.__name__} with id {row_id}")
    return row
