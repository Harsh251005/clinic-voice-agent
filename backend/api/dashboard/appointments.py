"""A clinic's appointments by day, and everything staff do to them: book,
change (who, why, doctor, time), cancel. Staff have the final say; the
rules are in clinic_agent.booking (staff section)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request

from api.dashboard import convert, schemas
from api.dashboard.access import open_clinic, staff_errors
from clinic_agent import booking
from clinic_agent.context import clinic_now
from clinic_agent.store import repo

router = APIRouter()


@router.get("/api/clinics/{clinic_id}/appointments", response_model=schemas.Day)
def day(day: date, request: Request, include_cancelled: bool = False, clinic_id: int = Depends(open_clinic)):
    with request.app.state.sessions() as s:
        rows = repo.appointments_on(s, clinic_id, day, include_cancelled=include_cancelled)
        booked = [a for a in rows if a.status == "booked"]
        week = sum(len(repo.appointments_on(s, clinic_id, day + timedelta(days=i))) for i in range(7))
        time_off = repo.time_off_overlapping(s, clinic_id, day, day)
        return schemas.Day(
            day=day, booked=len(booked),
            appointments=[
                convert.appointment(a, booking.appointment_problem(a, time_off) if a.status == "booked" else None)
                for a in rows
            ],
            booked_on_calls=sum(1 for a in booked if a.source == "voice"), next_7_days=week,
        )


@router.post("/api/clinics/{clinic_id}/appointments/{appointment_id}/cancel", response_model=schemas.Appointment)
def cancel(appointment_id: int, request: Request, clinic_id: int = Depends(open_clinic)):
    with staff_errors(), request.app.state.sessions() as s:
        appt = repo.in_clinic(s, repo.Appointment, appointment_id, clinic_id)
        repo.cancel_appointment(s, appt.id)
        return convert.appointment(repo.get_appointment(s, appt.id))


def _out(s, appt) -> schemas.Appointment:
    appt = repo.get_appointment(s, appt.id)
    problem = None
    if appt.status == "booked":
        day = appt.starts_at.date()
        problem = booking.appointment_problem(appt, repo.time_off_overlapping(s, appt.clinic_id, day, day))
    return convert.appointment(appt, problem)


@router.get("/api/clinics/{clinic_id}/doctors/{doctor_id}/free", response_model=schemas.FreeTimes)
def free(doctor_id: int, day: date, request: Request, clinic_id: int = Depends(open_clinic)):
    with staff_errors(), request.app.state.sessions() as s:
        now = clinic_now(repo.get_clinic(s, clinic_id).timezone)
        return schemas.FreeTimes(times=[t.time() for t in booking.free_times(s, clinic_id, doctor_id, day, now)])


@router.post("/api/clinics/{clinic_id}/appointments", response_model=schemas.Appointment)
def book(body: schemas.AppointmentIn, request: Request, clinic_id: int = Depends(open_clinic)):
    with staff_errors(), request.app.state.sessions() as s:
        appt = booking.staff_book(s, clinic_id, body.doctor_id, body.starts_at,
                                  body.patient_name, body.patient_phone, body.reason)
        return _out(s, appt)


@router.put("/api/clinics/{clinic_id}/appointments/{appointment_id}", response_model=schemas.Appointment)
def change(appointment_id: int, body: schemas.AppointmentIn, request: Request, clinic_id: int = Depends(open_clinic)):
    with staff_errors(), request.app.state.sessions() as s:
        appt = booking.staff_change(
            s, clinic_id, appointment_id, doctor_id=body.doctor_id, starts_at=body.starts_at,
            patient_name=body.patient_name, patient_phone=body.patient_phone, reason=body.reason,
        )
        return _out(s, appt)
