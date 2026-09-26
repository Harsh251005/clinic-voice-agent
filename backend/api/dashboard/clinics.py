"""A clinic's details, call link, and who may open it (the Team tab)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request

from api.dashboard import convert, schemas
from api.dashboard.access import Viewer, admin, open_clinic, staff_errors
from clinic_agent.context import clinic_now
from clinic_agent.store import repo

router = APIRouter()


def load(request: Request, clinic_id: int) -> schemas.Clinic:
    with request.app.state.sessions() as s:
        clinic = repo.get_clinic(s, clinic_id)
        today = clinic_now(clinic.timezone).date()
        time_off = repo.time_off_overlapping(s, clinic_id, today, today + timedelta(days=5 * 366))
        upcoming = repo.upcoming_counts(s, clinic_id, clinic_now(clinic.timezone))
        return convert.clinic(clinic, time_off, upcoming, request.app.state.cfg.public_base_url)


@router.get("/api/clinics/{clinic_id}", response_model=schemas.Clinic)
def get_clinic(request: Request, clinic_id: int = Depends(open_clinic)):
    return load(request, clinic_id)


@router.post("/api/clinics", response_model=schemas.ClinicSummary)
def create_clinic(body: schemas.NewClinic, request: Request, viewer: Viewer = Depends(admin)):
    with staff_errors(), request.app.state.sessions() as s:
        c = repo.create_clinic(s, name=body.name.strip(), address=body.address.strip(), phone=body.phone.strip())
        return schemas.ClinicSummary(id=c.id, name=c.name, slug=c.slug, staff=viewer.is_staff(c.id))


@router.patch("/api/clinics/{clinic_id}", response_model=schemas.Clinic)
def update_clinic(body: schemas.ClinicDetails, request: Request, clinic_id: int = Depends(open_clinic)):
    fields = body.model_dump()
    fields.update(name=body.name.strip(), address=body.address.strip(), phone=body.phone.strip())
    with staff_errors(), request.app.state.sessions() as s:
        repo.update_clinic(s, clinic_id, **fields)
    return load(request, clinic_id)


@router.put("/api/clinics/{clinic_id}/slug", response_model=schemas.Clinic)
def set_slug(body: schemas.SlugIn, request: Request, clinic_id: int = Depends(open_clinic)):
    with staff_errors(), request.app.state.sessions() as s:
        repo.set_slug(s, clinic_id, body.slug.strip().lower())
    return load(request, clinic_id)


# ---------- team (admins only) ----------

@router.get("/api/clinics/{clinic_id}/members", response_model=list[schemas.Member], dependencies=[Depends(admin)])
def members(request: Request, clinic_id: int = Depends(open_clinic)):
    with request.app.state.sessions() as s:
        return [schemas.Member(id=m.id, email=m.email) for m in repo.list_members(s, clinic_id)]


@router.post("/api/clinics/{clinic_id}/members", response_model=schemas.Member, dependencies=[Depends(admin)])
def add_member(body: schemas.MemberIn, request: Request, clinic_id: int = Depends(open_clinic)):
    with staff_errors(), request.app.state.sessions() as s:
        m = repo.add_member(s, clinic_id, body.email)
        return schemas.Member(id=m.id, email=m.email)


@router.delete("/api/clinics/{clinic_id}/members/{member_id}", dependencies=[Depends(admin)])
def remove_member(member_id: int, request: Request, clinic_id: int = Depends(open_clinic)) -> dict:
    with staff_errors(), request.app.state.sessions() as s:
        repo.remove_member(s, repo.in_clinic(s, repo.ClinicMember, member_id, clinic_id).id)
    return {"ok": True}
