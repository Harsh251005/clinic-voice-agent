"""The dashboard's JSON API under /api. The Next.js app (frontend/) is only
screens; every rule and access check lives here and in repo.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dashboard import admin, appointments, auth, clinics, doctors, notes
from api.dashboard.access import same_site
from clinic_agent.config import Settings


def router(cfg: Settings) -> APIRouter:
    r = APIRouter(dependencies=[Depends(same_site)])
    r.include_router(auth.router(cfg))
    for area in (clinics, doctors, notes, appointments, admin):
        r.include_router(area.router)
    return r
