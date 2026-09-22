"""Doctors, their weekly hours, and the schedule patterns that prefill them."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.dashboard import convert, patterns, schemas
from api.dashboard.access import current_viewer, open_clinic, staff_errors
from clinic_agent.context import clinic_now
from clinic_agent.store import repo

router = APIRouter()


def _rows(items: list[schemas.Sitting]):
    return [(i.weekday, i.start, i.end) for i in items]


def _now(s, clinic_id: int):
    return clinic_now(repo.get_clinic(s, clinic_id).timezone)


def _out(s, doctor) -> schemas.Doctor:
    return convert.doctor(doctor, repo.upcoming_counts(s, doctor.clinic_id, _now(s, doctor.clinic_id)).get(doctor.id, 0))


@router.post("/api/clinics/{clinic_id}/doctors", response_model=schemas.Doctor)
def add_doctor(body: schemas.NewDoctor, request: Request, clinic_id: int = Depends(open_clinic)):
    fields = body.model_dump(exclude={"hours"})
    fields.update(name=body.name.strip(), specialty=body.specialty.strip())
    with staff_errors(), request.app.state.sessions() as s:
        # Hours are validated before the doctor exists, so bad hours add nobody.
        repo.check_sittings(_rows(body.hours))
        doctor = repo.add_doctor(s, clinic_id, **fields)
        repo.set_doctor_hours(s, doctor.id, _rows(body.hours))
        return _out(s, repo.in_clinic(s, repo.Doctor, doctor.id, clinic_id))


@router.patch("/api/clinics/{clinic_id}/doctors/{doctor_id}", response_model=schemas.Doctor)
def update_doctor(doctor_id: int, body: schemas.DoctorPatch, request: Request, clinic_id: int = Depends(open_clinic)):
    fields = body.model_dump(exclude_none=True)
    for key in ("name", "specialty"):
        if key in fields:
            fields[key] = fields[key].strip()
    with staff_errors(), request.app.state.sessions() as s:
        doctor = repo.in_clinic(s, repo.Doctor, doctor_id, clinic_id)
        repo.update_doctor(s, doctor.id, **fields)
        return _out(s, doctor)


@router.put("/api/clinics/{clinic_id}/doctors/{doctor_id}/hours", response_model=schemas.Doctor)
def set_hours(doctor_id: int, body: schemas.HoursIn, request: Request, clinic_id: int = Depends(open_clinic)):
    with staff_errors(), request.app.state.sessions() as s:
        doctor = repo.in_clinic(s, repo.Doctor, doctor_id, clinic_id)
        repo.set_doctor_hours(s, doctor.id, _rows(body.sittings))
        s.refresh(doctor)
        return _out(s, doctor)


@router.delete("/api/clinics/{clinic_id}/doctors/{doctor_id}")
def delete_doctor(doctor_id: int, request: Request, clinic_id: int = Depends(open_clinic)) -> dict:
    """Remove a doctor for good (deactivating keeps them). Refused with a
    422 while they have upcoming bookings."""
    with staff_errors(), request.app.state.sessions() as s:
        doctor = repo.in_clinic(s, repo.Doctor, doctor_id, clinic_id)
        repo.delete_doctor(s, doctor.id, _now(s, clinic_id))
    return {"ok": True}


@router.post("/api/hours/preview", response_model=schemas.HoursText, dependencies=[Depends(current_viewer)])
def preview(body: schemas.HoursIn):
    """How the receptionist will describe these (unsaved) hours."""
    return schemas.HoursText(text=convert.hours_text(body.sittings))


@router.get("/api/hours/patterns", response_model=list[schemas.Pattern], dependencies=[Depends(current_viewer)])
def hour_patterns():
    return [
        schemas.Pattern(name=name, sittings=[schemas.Sitting(weekday=w, start=a, end=b) for w, a, b in rows])
        for name, rows in patterns.PRESETS.items()
    ]
