"""FAQ answers and time off (leave and holidays)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.dashboard import convert, schemas
from api.dashboard.access import open_clinic, staff_errors
from clinic_agent import booking
from clinic_agent.context import clinic_now
from clinic_agent.store import repo

router = APIRouter()


@router.post("/api/clinics/{clinic_id}/faq", response_model=schemas.Faq)
def add_faq(body: schemas.FaqIn, request: Request, clinic_id: int = Depends(open_clinic)):
    with staff_errors(), request.app.state.sessions() as s:
        f = repo.add_faq(s, clinic_id, body.question.strip(), body.answer.strip())
        return schemas.Faq(id=f.id, question=f.question, answer=f.answer)


@router.delete("/api/clinics/{clinic_id}/faq/{faq_id}")
def delete_faq(faq_id: int, request: Request, clinic_id: int = Depends(open_clinic)) -> dict:
    with staff_errors(), request.app.state.sessions() as s:
        repo.delete_faq(s, repo.in_clinic(s, repo.ClinicFaq, faq_id, clinic_id).id)
    return {"ok": True}


@router.post("/api/clinics/{clinic_id}/time-off", response_model=schemas.TimeOffAdded)
def add_time_off(body: schemas.TimeOffIn, request: Request, clinic_id: int = Depends(open_clinic)):
    """Leave or a holiday. Bookings already on those days stay booked; they
    come back as `clashes` so staff can call those patients."""
    with staff_errors(), request.app.state.sessions() as s:
        if body.doctor_id is not None:  # the doctor must be this clinic's too
            repo.in_clinic(s, repo.Doctor, body.doctor_id, clinic_id)
        t = repo.add_time_off(s, clinic_id, body.date_from, body.date_to,
                              doctor_id=body.doctor_id, reason=body.reason.strip())
        now = clinic_now(repo.get_clinic(s, clinic_id).timezone)
        clashes = [a for a in repo.booked_between(s, clinic_id, t.date_from, t.date_to, t.doctor_id)
                   if a.starts_at >= now]
        return schemas.TimeOffAdded(
            id=t.id, date_from=t.date_from, date_to=t.date_to, doctor_id=t.doctor_id, reason=t.reason,
            clashes=[convert.appointment(a, booking.appointment_problem(a, [t])) for a in clashes],
        )


@router.delete("/api/clinics/{clinic_id}/time-off/{time_off_id}")
def delete_time_off(time_off_id: int, request: Request, clinic_id: int = Depends(open_clinic)) -> dict:
    with staff_errors(), request.app.state.sessions() as s:
        repo.delete_time_off(s, repo.in_clinic(s, repo.TimeOff, time_off_id, clinic_id).id)
    return {"ok": True}
