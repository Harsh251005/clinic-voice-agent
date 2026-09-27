"""A clinic's own calls, for its staff: when, how long, what changed, and
what was said. Only the conversation: the tools the receptionist used and
vendor errors stay in the operator's trace (/api/admin). Staff also see
each time ClinicDesk support opened a transcript, with the reason given."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.dashboard import convert, schemas
from api.dashboard.access import clinic_staff, staff_errors
from api.dashboard.admin import dropped_before
from clinic_agent.store import repo
from clinic_agent.store.models import utc_now

router = APIRouter(prefix="/api/clinics/{clinic_id}/calls")


def _change(s, clinic_id: int, change: dict) -> schemas.ClinicCallChange:
    try:
        appt = repo.in_clinic(s, repo.Appointment, change["id"], clinic_id)
    except repo.NotFound:  # deleted since (its doctor was removed)
        return schemas.ClinicCallChange(action=change["action"], appointment_id=change["id"],
                                        patient_name=None, doctor_name=None, starts_at=None)
    return schemas.ClinicCallChange(action=change["action"], appointment_id=appt.id, patient_name=appt.patient.name,
                                    doctor_name=appt.doctor.name, starts_at=appt.starts_at)


def _call(s, call, request: Request) -> schemas.ClinicCall:
    duration = round((call.ended_at - call.started_at).total_seconds()) if call.ended_at else None
    return schemas.ClinicCall(
        id=call.id, started_at=convert.utc(call.started_at), duration_s=duration,
        status=convert.call_status(call, dropped_before(request, utc_now())), outcome=call.outcome,
        changes=[_change(s, call.clinic_id, c) for c in call.appointments],
    )


@router.get("", response_model=list[schemas.ClinicCall])
def calls(request: Request, before_id: int | None = None, clinic_id: int = Depends(clinic_staff)):
    with request.app.state.sessions() as s:
        return [_call(s, c, request) for c in repo.list_calls(s, clinic_id=clinic_id, before_id=before_id)]


@router.get("/{call_id}", response_model=schemas.ClinicCallDetail)
def call(call_id: int, request: Request, clinic_id: int = Depends(clinic_staff)):
    with staff_errors(), request.app.state.sessions() as s:
        found = repo.in_clinic(s, repo.Call, call_id, clinic_id)
        kept = repo.has_transcript(s, found.id)
        items = repo.get_transcript(s, found.id).items if kept else []
        return schemas.ClinicCallDetail(
            **_call(s, found, request).model_dump(),
            transcript_kept=kept,
            conversation=[
                schemas.SpokenLine(t_ms=i["t_ms"], role=i["role"], text=i["text"], interrupted=i.get("interrupted", False))
                for i in items if i["role"] in ("caller", "agent")
            ],
            support_views=[schemas.SupportView(reason=a.reason, at=convert.utc(a.at))
                           for a in repo.transcript_accesses(s, found.id)],
        )
