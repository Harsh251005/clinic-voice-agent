"""Admin > Receptionist (/api/admin/receptionist): how the receptionist
behaves on every clinic's calls (Harsh, 2026-11-10). Admins only; no patient
data. Fields, limits and defaults: clinic_agent/receptionist_settings.py. A
call reads them when it starts (call_settings.py), so a saved change applies
from the next call, no restart.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dashboard import schemas
from api.dashboard.access import admin, staff_errors
from clinic_agent import receptionist_settings as rs
from clinic_agent.call_settings import merge
from clinic_agent.config import ConfigError
from clinic_agent.lines import line_for
from clinic_agent.prompts import RULES
from clinic_agent.providers import build_tts, check_voice, voice_catalogue
from clinic_agent.providers.defaults import BLANK_MEANS, SARVAM_TTS_MODEL, SARVAM_TTS_SPEAKER
from clinic_agent.store import repo

router = APIRouter(dependencies=[Depends(admin)])

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


def _with(row, scope, changes: dict) -> SimpleNamespace:
    """`row` as it would be after `changes` (each checked first: ValueError)."""
    values = {f.name: getattr(row, f.name) for f in scope}
    values.update({name: rs.checked(rs.field(scope, name), v) for name, v in changes.items()})
    return SimpleNamespace(**values)


def _voices_work(request: Request, system, clinics) -> None:
    """Every clinic's voice must still build after a change: a speaker the
    voice model doesn't have would leave that clinic's calls unanswered
    (seen 2026-11-10: suhani on bulbul:v4-flash). Without a voice key there
    is nothing to try, so nothing is refused."""
    for clinic in clinics:
        cfg = merge(request.app.state.cfg, system, clinic).cfg
        try:
            build_tts(cfg, line_for(cfg, LANGUAGE).tts)
        except ConfigError:
            return
        except ValueError as err:
            why = str(err).split(". Please choose", 1)[0]
            raise HTTPException(422, f"{clinic.name}: {why}. Pick a speaker that voice model has.") from None


@router.get("/api/admin/receptionist", response_model=schemas.SystemSettingsOut)
def read(request: Request):
    with request.app.state.sessions() as s:
        return _out(repo.system_settings(s))


@router.put("/api/admin/receptionist", response_model=schemas.SystemSettingsOut)
def save(body: schemas.SystemSettingsIn, request: Request):
    """Only the fields sent change; each is checked (422 with the reason)."""
    changes = body.model_dump(exclude_unset=True)
    with staff_errors(), request.app.state.sessions() as s:
        return _out(repo.update_system_settings(s, **changes))


# ---------- each clinic's own (receptionist_settings.CLINIC), admins only ----------

def _clinic_out(clinic) -> schemas.ClinicReceptionistOut:
    return schemas.ClinicReceptionistOut(
        clinic_id=clinic.id, clinic_name=clinic.name,
        **{f.name: getattr(clinic, f.name) for f in rs.CLINIC},
        speaker_default=SARVAM_TTS_SPEAKER, model_default=SARVAM_TTS_MODEL,
        voices=[schemas.VoiceModel(
            name=m.name, default_speaker=m.default_speaker, pitch=m.pitch,
            speakers=[schemas.VoiceSpeaker(name=v.name, label=v.label) for v in m.speakers],
        ) for m in voice_catalogue()],
        instructions_max_words=rs.INSTRUCTIONS_MAX_WORDS, directions_max_chars=rs.DIRECTIONS_MAX_CHARS,
        limits={f.name: schemas.Limit(low=f.low, high=f.high, default=f.default)
                for f in rs.CLINIC if f.kind == "number"},
    )


@router.get("/api/admin/clinics/{clinic_id}/receptionist", response_model=schemas.ClinicReceptionistOut)
def read_clinic(clinic_id: int, request: Request):
    with staff_errors(), request.app.state.sessions() as s:
        return _clinic_out(repo.get_clinic(s, clinic_id))


@router.put("/api/admin/clinics/{clinic_id}/receptionist", response_model=schemas.ClinicReceptionistOut)
def save_clinic(clinic_id: int, body: schemas.ClinicReceptionistIn, request: Request):
    """Only the fields sent change; each is checked (422 with the reason)."""
    changes = body.model_dump(exclude_unset=True)
    with staff_errors(), request.app.state.sessions() as s:
        clinic = repo.get_clinic(s, clinic_id)
        after = _with(clinic, rs.CLINIC, changes)
        after.name = clinic.name
        if {"tts_model", "tts_speaker"} & changes.keys():
            # A new voice is one from the pick-lists (women's voices the model has), key or no key.
            try:
                check_voice(after.tts_model, after.tts_speaker)
            except ValueError as err:
                raise HTTPException(422, f"{clinic.name}: {err}") from None
        _voices_work(request, repo.system_settings(s), [after])
        return _clinic_out(repo.update_clinic_receptionist(s, clinic_id, **changes))
