"""A clinic's appointments by day, and staff cancellation."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request

from api.dashboard import convert, schemas
from api.dashboard.access import open_clinic, staff_errors
from clinic_agent import booking
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
