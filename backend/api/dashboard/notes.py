"""FAQ answers and time off (leave and holidays)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.dashboard import schemas
from api.dashboard.access import open_clinic, staff_errors
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


@router.post("/api/clinics/{clinic_id}/time-off", response_model=schemas.TimeOff)
def add_time_off(body: schemas.TimeOffIn, request: Request, clinic_id: int = Depends(open_clinic)):
    with staff_errors(), request.app.state.sessions() as s:
        if body.doctor_id is not None:  # the doctor must be this clinic's too
            repo.in_clinic(s, repo.Doctor, body.doctor_id, clinic_id)
        t = repo.add_time_off(s, clinic_id, body.date_from, body.date_to,
                              doctor_id=body.doctor_id, reason=body.reason.strip())
        return schemas.TimeOff(id=t.id, date_from=t.date_from, date_to=t.date_to,
                               doctor_id=t.doctor_id, reason=t.reason)


@router.delete("/api/clinics/{clinic_id}/time-off/{time_off_id}")
def delete_time_off(time_off_id: int, request: Request, clinic_id: int = Depends(open_clinic)) -> dict:
    with staff_errors(), request.app.state.sessions() as s:
        repo.delete_time_off(s, repo.in_clinic(s, repo.TimeOff, time_off_id, clinic_id).id)
    return {"ok": True}
