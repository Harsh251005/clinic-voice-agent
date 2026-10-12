"""A clinic's own calls, for its staff: when, how long, what changed, and
what was said. Only the conversation: the tools the receptionist used and
vendor errors stay in the operator's trace (/api/admin). Staff also see
each time ClinicDesk support opened a transcript, with the reason given.

Staff can also call their own receptionist (POST /test): a real call that
books for real, marked as a test, left out of the counts, and erasable with
everything it changed (DELETE /{call_id})."""

from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dashboard import convert, schemas
from api.dashboard.access import clinic_staff, staff_errors
from api.dashboard.admin import dropped_before
from api.passes import call_pass, offered
from clinic_agent import booking
from clinic_agent.context import clinic_now
from clinic_agent.lines import NAMES
from clinic_agent.store import repo
from clinic_agent.store.models import utc_now

logger = logging.getLogger("clinic-agent.api")
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
        language=call.language, test=call.test,
        changes=[_change(s, call.clinic_id, c) for c in call.appointments],
    )


@router.get("", response_model=list[schemas.ClinicCall])
def calls(request: Request, before_id: int | None = None, clinic_id: int = Depends(clinic_staff)):
    with request.app.state.sessions() as s:
        return [_call(s, c, request) for c in repo.list_calls(s, clinic_id=clinic_id, before_id=before_id)]


@router.get("/today", response_model=schemas.CallsToday)
def today(request: Request, clinic_id: int = Depends(clinic_staff)):
    """Declared before /{call_id}, which would otherwise catch "today"."""
    with request.app.state.sessions() as s:
        tz = repo.get_clinic(s, clinic_id).timezone
        midnight = datetime.combine(clinic_now(tz).date(), time(0), tzinfo=ZoneInfo(tz))
        since = midnight.astimezone(UTC).replace(tzinfo=None)  # stored naive UTC
        found = [_call(s, c, request) for c in repo.list_calls(s, clinic_id=clinic_id, since=since, limit=None)
                 if not c.test]  # staff's own test calls aren't patients calling
        return schemas.CallsToday(
            calls=len(found),
            changed=sum(1 for c in found if c.changes),
            questions=sum(1 for c in found if c.outcome == "info_only"),
            unhelped=[c for c in found if c.status == "dropped" or c.outcome == "failed"],
        )


@router.post("/test", response_model=schemas.TestCallPass)
def test_call(body: schemas.TestCallRequest, request: Request, clinic_id: int = Depends(clinic_staff)):
    """A pass for staff to call their own receptionist, exactly as a patient would."""
    with request.app.state.sessions() as s:
        clinic = repo.get_clinic(s, clinic_id)
        if not clinic.active:
            raise HTTPException(409, "Your receptionist is paused by ClinicDesk support, so it can't take test calls either.")
        if body.language not in offered(s):
            raise HTTPException(409, f"Calls in {NAMES[body.language]} aren't available right now.")
    p = call_pass(request.app.state.cfg, clinic.id, clinic.slug, body.language, test=True)
    logger.info("test call pass for clinic %s, language %s: room %s", clinic.id, body.language, p.room)
    return schemas.TestCallPass(url=p.url, token=p.token, room=p.room)


def _finished_tests(s, clinic_id: int, request: Request) -> tuple[list, list]:
    """(every test call, the ones that have ended)."""
    tests = repo.test_calls(s, clinic_id)
    cutoff = dropped_before(request, utc_now())
    return tests, [c for c in tests if convert.call_status(c, cutoff) != "live"]


@router.get("/tests", response_model=schemas.TestCalls)
def tests(request: Request, clinic_id: int = Depends(clinic_staff)):
    """How many test calls are on record, for Talk to receptionist's "erase all"."""
    with request.app.state.sessions() as s:
        every, done = _finished_tests(s, clinic_id, request)
        return schemas.TestCalls(count=len(every), erasable=len(done))


@router.delete("/tests", response_model=schemas.TestCallsErased)
def erase_tests(request: Request, clinic_id: int = Depends(clinic_staff)):
    """Erase every finished test call at once, with everything they changed:
    all of them or none (newest first). A call still going is left alone."""
    with staff_errors(), request.app.state.sessions() as s:
        _, done = _finished_tests(s, clinic_id, request)
        booking.erase_test_calls(s, clinic_id, [c.id for c in done])
    logger.info("erased %s test calls of clinic %s", len(done), clinic_id)
    return schemas.TestCallsErased(erased=len(done))


@router.get("/by-room/{room}", response_model=schemas.ClinicCall)
def call_in_room(room: str, request: Request, clinic_id: int = Depends(clinic_staff)):
    """The call that took place in this room: how the test-call screen finds
    the call it just made (the worker opens its record as it answers)."""
    with staff_errors(), request.app.state.sessions() as s:
        return _call(s, repo.call_in_room(s, clinic_id, room), request)


@router.delete("/{call_id}", status_code=204)
def erase(call_id: int, request: Request, clinic_id: int = Depends(clinic_staff)):
    """Erase a test call: undo every booking, cancellation and move it made,
    then delete its record, trace and transcript. Patients' calls can't be."""
    with staff_errors(), request.app.state.sessions() as s:
        found = repo.in_clinic(s, repo.Call, call_id, clinic_id)
        if not found.test:
            raise ValueError("Only test calls can be erased. Patients' calls are kept.")
        if convert.call_status(found, dropped_before(request, utc_now())) == "live":
            raise HTTPException(409, "This test call is still going. Erase it once it has ended.")
        booking.erase_test_call(s, clinic_id, found.id)
    logger.info("erased test call %s of clinic %s", call_id, clinic_id)


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
