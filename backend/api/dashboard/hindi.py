"""Names in Hindi, suggested from the English name (providers/hindi.py).

The settings forms ask for a suggestion while staff type; saving a clinic or
doctor with the Hindi box blank fills it in the same way, so every name has
one fixed spelling. A failed suggestion never blocks a save: the name stays
blank (the Hindi line then spells it itself) and the operator sees a problem.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dashboard import schemas
from api.dashboard.access import open_clinic
from clinic_agent import incidents
from clinic_agent.config import ConfigError
from clinic_agent.providers import hindi
from clinic_agent.store import repo
from clinic_agent.store.models import utc_now

logger = logging.getLogger("clinic-agent.api")
router = APIRouter()


def suggestion(request: Request, name: str, clinic_id: int) -> str:
    """The Hindi name for `name`, spelt like the clinic's other names, or ""
    if none could be had (reported)."""
    with request.app.state.sessions() as s:
        clinic = repo.get_clinic(s, clinic_id)
        known = hindi.glossary([(clinic.name, clinic.name_hi), *((d.name, d.name_hi) for d in clinic.doctors)])
    try:
        return hindi.suggest(request.app.state.cfg, name, known)
    except (ConfigError, hindi.NoSuggestion) as err:
        logger.warning("no Hindi name suggestion: %s", err)
        with request.app.state.sessions() as s:
            incidents.report(s, "hindi_names_failing", utc_now(), clinic_id=clinic_id,
                             subject=type(err).__name__, detail=str(err)[:200])
        return ""


@router.post("/api/clinics/{clinic_id}/hindi-name", response_model=schemas.HindiName)
def suggest(body: schemas.NameIn, request: Request, clinic_id: int = Depends(open_clinic)):
    """For the settings forms: the suggestion staff see in the Hindi box."""
    name_hi = suggestion(request, body.name, clinic_id)
    if body.name.strip() and not name_hi:
        raise HTTPException(503, "No suggestion just now. Type it in Hindi, or leave it blank.")
    return schemas.HindiName(name_hi=name_hi)
