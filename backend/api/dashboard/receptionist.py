"""Admin > Receptionist (/api/admin/receptionist): how the receptionist
behaves on every clinic's calls (Harsh, 2026-11-10). Admins only; no patient
data. Fields, limits and defaults: clinic_agent/receptionist_settings.py. A
call reads them when it starts (call_settings.py), so a saved change applies
from the next call, no restart.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.dashboard import schemas
from api.dashboard.access import admin, staff_errors
from clinic_agent import receptionist_settings as rs
from clinic_agent.prompts import RULES
from clinic_agent.providers.defaults import BLANK_MEANS
from clinic_agent.store import repo

router = APIRouter(prefix="/api/admin/receptionist", dependencies=[Depends(admin)])

LANGUAGE = "hi"  # the one line


def _out(row) -> schemas.SystemSettingsOut:
    values = {f.name: getattr(row, f.name) for f in rs.SYSTEM}
    return schemas.SystemSettingsOut(
        **values,
        default_rules=RULES[LANGUAGE],
        rules_max_words=rs.RULES_MAX_WORDS,
        blank_means={k: v for k, v in BLANK_MEANS.items() if k in values},
        limits={f.name: schemas.Limit(low=f.low, high=f.high, default=f.default)
                for f in rs.SYSTEM if f.kind == "number"},
        llm_vendors=list(rs.LLM_VENDORS),
    )


@router.get("", response_model=schemas.SystemSettingsOut)
def read(request: Request):
    with request.app.state.sessions() as s:
        return _out(repo.system_settings(s))


@router.put("", response_model=schemas.SystemSettingsOut)
def save(body: schemas.SystemSettingsIn, request: Request):
    """Only the fields sent change; each is checked (422 with the reason)."""
    changes = body.model_dump(exclude_unset=True)
    with staff_errors(), request.app.state.sessions() as s:
        return _out(repo.update_system_settings(s, **changes))
