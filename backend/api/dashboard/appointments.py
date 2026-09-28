"""A clinic's diary (a day, a week, a search), and everything staff do to
appointments: book, change (who, why, doctor, time), cancel and undo it,
mark the visit (arrived, done, no-show). Staff have the final say; the
rules are in clinic_agent.booking (staff section)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request

from api.dashboard import convert, schemas
from api.dashboard.access import clinic_staff, staff_errors
from clinic_agent import booking
from clinic_agent.context import clinic_now
from clinic_agent.store import repo

router = APIRouter()


@router.get("/api/clinics/{clinic_id}/appointments", response_model=schemas.Day)
def day(day: date, request: Request, include_cancelled: bool = False, clinic_id: int = Depends(clinic_staff)):
    with request.app.state.sessions() as s:
        clinic = repo.get_clinic(s, clinic_id)
        now = clinic_now(clinic.timezone)
        rows = repo.appointments_on(s, clinic_id, day, include_cancelled=include_cancelled)
        booked = [a for a in rows if a.status == "booked"]
        week = len(repo.booked_between(s, clinic_id, day, day + timedelta(days=6)))
        time_off = repo.time_off_overlapping(s, clinic_id, day, day)
        with_bookings = {a.doctor_id for a in rows}
        doctors = []
        for d in clinic.doctors:
            if not (d.active or d.id in with_bookings):
                continue
            plan = booking.day_plan(s, d, day, time_off, now)
            doctors.append(schemas.DoctorDay(
                id=d.id, name=d.name, slot_minutes=d.slot_minutes, active=d.active,
                sittings=[schemas.Span(start=a, end=b) for a, b in plan.sittings],
                off=plan.off, free=[t.time() for t in plan.free],
            ))
        return schemas.Day(
            day=day, booked=len(booked), doctors=doctors,
            appointments=[
                convert.appointment(a, booking.appointment_problem(a, time_off) if a.status == "booked" else None)
                for a in rows
            ],
            booked_on_calls=sum(1 for a in booked if a.source == "voice"), next_7_days=week,
        )


@router.get("/api/clinics/{clinic_id}/appointments/week", response_model=schemas.Week)
def week(start: date, request: Request, clinic_id: int = Depends(clinic_staff)):
    """Seven days from `start`: booked appointments and each doctor's day."""
    end = start + timedelta(days=6)
    with request.app.state.sessions() as s:
        clinic = repo.get_clinic(s, clinic_id)
        now = clinic_now(clinic.timezone)
        rows = repo.booked_between(s, clinic_id, start, end)
        time_off = repo.time_off_overlapping(s, clinic_id, start, end)
        with_bookings = {a.doctor_id for a in rows}
        doctors = [d for d in clinic.doctors if d.active or d.id in with_bookings]
        days = []
        for i in range(7):
            day = start + timedelta(days=i)
            on_day = [a for a in rows if a.starts_at.date() == day]
            plans = [(d, booking.day_plan(s, d, day, time_off, now)) for d in doctors]
            days.append(schemas.WeekDay(
                day=day,
                appointments=[convert.appointment(a, booking.appointment_problem(a, time_off)) for a in on_day],
                doctors=[
                    schemas.WeekDoctorDay(doctor_id=d.id, sits=bool(p.sittings), off=p.off, free=len(p.free))
                    for d, p in plans
                ],
            ))
        return schemas.Week(start=start, doctors=[schemas.DoctorRef(id=d.id, name=d.name) for d in doctors], days=days)


@router.get("/api/clinics/{clinic_id}/appointments/search", response_model=list[schemas.Appointment])
def search(request: Request, q: str = Query(max_length=100), clinic_id: int = Depends(clinic_staff)):
    """By patient name or mobile number: upcoming first, then the most recent past."""
    if len(q.strip()) < 2:
        return []
    with request.app.state.sessions() as s:
        today = clinic_now(repo.get_clinic(s, clinic_id).timezone).date()
        rows = repo.search_appointments(s, clinic_id, q, today)
        days = [a.starts_at.date() for a in rows if a.status == "booked"]
        time_off = repo.time_off_overlapping(s, clinic_id, min(days), max(days)) if days else []
        return [
            convert.appointment(a, booking.appointment_problem(a, time_off) if a.status == "booked" else None)
            for a in rows
        ]


@router.post("/api/clinics/{clinic_id}/appointments/{appointment_id}/cancel", response_model=schemas.Appointment)
def cancel(appointment_id: int, request: Request, clinic_id: int = Depends(clinic_staff)):
    with staff_errors(), request.app.state.sessions() as s:
        appt = repo.in_clinic(s, repo.Appointment, appointment_id, clinic_id)
        repo.cancel_appointment(s, appt.id)
        return convert.appointment(repo.get_appointment(s, appt.id))


@router.post("/api/clinics/{clinic_id}/appointments/{appointment_id}/restore", response_model=schemas.Appointment)
def restore(appointment_id: int, request: Request, clinic_id: int = Depends(clinic_staff)):
    """Undo a cancellation, if the slot is still free."""
    with staff_errors(), request.app.state.sessions() as s:
        return _out(s, booking.staff_restore(s, clinic_id, appointment_id))


@router.post("/api/clinics/{clinic_id}/appointments/{appointment_id}/visit", response_model=schemas.Appointment)
def visit(appointment_id: int, body: schemas.VisitIn, request: Request, clinic_id: int = Depends(clinic_staff)):
    with staff_errors(), request.app.state.sessions() as s:
        now = clinic_now(repo.get_clinic(s, clinic_id).timezone)
        return _out(s, booking.staff_visit(s, clinic_id, appointment_id, body.visit, now))


def _out(s, appt) -> schemas.Appointment:
    appt = repo.get_appointment(s, appt.id)
    problem = None
    if appt.status == "booked":
        day = appt.starts_at.date()
        problem = booking.appointment_problem(appt, repo.time_off_overlapping(s, appt.clinic_id, day, day))
    return convert.appointment(appt, problem)


@router.get("/api/clinics/{clinic_id}/doctors/{doctor_id}/free", response_model=schemas.FreeTimes)
def free(doctor_id: int, day: date, request: Request, clinic_id: int = Depends(clinic_staff)):
    with staff_errors(), request.app.state.sessions() as s:
        now = clinic_now(repo.get_clinic(s, clinic_id).timezone)
        return schemas.FreeTimes(times=[t.time() for t in booking.free_times(s, clinic_id, doctor_id, day, now)])


@router.post("/api/clinics/{clinic_id}/appointments", response_model=schemas.Appointment)
def book(body: schemas.AppointmentIn, request: Request, clinic_id: int = Depends(clinic_staff)):
    with staff_errors(), request.app.state.sessions() as s:
        appt = booking.staff_book(s, clinic_id, body.doctor_id, body.starts_at,
                                  body.patient_name, body.patient_phone, body.reason)
        return _out(s, appt)


@router.put("/api/clinics/{clinic_id}/appointments/{appointment_id}", response_model=schemas.Appointment)
def change(appointment_id: int, body: schemas.AppointmentIn, request: Request, clinic_id: int = Depends(clinic_staff)):
    with staff_errors(), request.app.state.sessions() as s:
        appt = booking.staff_change(
            s, clinic_id, appointment_id, doctor_id=body.doctor_id, starts_at=body.starts_at,
            patient_name=body.patient_name, patient_phone=body.patient_phone, reason=body.reason,
        )
        return _out(s, appt)
