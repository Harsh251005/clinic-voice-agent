"""Problems (incidents) for the two dashboards, in two voices.

The clinic reads plain words and what to do about it, never vendor or
server names. The operator (admin) reads what broke and where to look.
Which problems a clinic sees is `incidents.KINDS[kind].clinic_sees`.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request

from api.dashboard import convert, schemas
from api.dashboard.access import Viewer, admin, open_clinic, staff_errors
from clinic_agent import incidents
from clinic_agent.store import repo
from clinic_agent.store.models import utc_now

router = APIRouter()

HISTORY = timedelta(days=7)  # resolved problems still listed
RANK = {"critical": 0, "warning": 1, "info": 2}

REASONS = {  # why a patient's call page gave up (incidents.CONNECT_FAILURES)
    "mic_blocked": "their browser blocked the microphone",
    "no_mic": "their phone or computer has no microphone",
    "connect_failed": "the call couldn't connect",
    "no_answer": "the receptionist didn't answer",
    "dropped": "the call dropped midway",
}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def clinic_words(inc: repo.Incident, clinic_id: int) -> tuple[str, str, str | None]:
    """(what's wrong, what to do, where to look) for the clinic's staff."""
    base = f"/clinics/{clinic_id}"
    match inc.kind:
        case "worker_offline":
            return ("Your receptionist is offline. Patients calling now can't reach it.",
                    "ClinicDesk support sees this too. Until it's back, patients can still ring the clinic's own phone.", None)
        case "calls_failing":
            return ("Several calls to your receptionist failed in the last hour.",
                    "Open Calls to see who called, and ring them back.", f"{base}/calls")
        case "patients_cant_connect":
            why = REASONS.get(inc.subject, "their call didn't go through")
            return (f"{_plural(inc.count, 'patient')} couldn't reach your receptionist: {why}.",
                    "If it keeps happening, tell ClinicDesk support.", None)
        case "no_doctors":
            return ("Callers can't book: no doctor is taking bookings.",
                    "Add a doctor, or turn one back on, in Clinic settings.", f"{base}/setup?tab=doctors")
        case "doctor_no_hours":
            return (f"Callers can't book {inc.detail}: no weekly hours are set.",
                    "Set their hours in Clinic settings, Weekly hours.", f"{base}/setup?tab=hours")
        case "clinic_paused":
            return ("Your receptionist is paused by ClinicDesk support. It isn't answering calls.",
                    "Contact ClinicDesk support to turn it back on.", None)
        case "bookings_need_call":
            n = int(inc.detail or 0)
            return (f"{_plural(n, 'upcoming booking')} can't go ahead as booked.",
                    "Call the patients: Today lists them under Needs attention.", f"{base}/today")
    return ("Something needs attention.", "", None)


def admin_words(inc: repo.Incident, clinic: str | None) -> tuple[str, str, str | None]:
    """(what broke, what to do, where to look) for the operator."""
    at = f"{clinic}: " if clinic else ""
    match inc.kind:
        case "worker_offline":
            since = "never checked in" if inc.detail == "never" else f"last checked in {inc.detail}"
            return (f"Receptionist offline: no worker connected to LiveKit ({since}).",
                    "Start or restart the worker: uv run python main.py start", None)
        case "vendor_errors":
            return (f"{inc.subject} is failing: {inc.detail}.",
                    "Check the vendor's status page and the API key.", "/admin/errors")
        case "calls_failing":
            return (f"{at}{inc.detail} failed or dropped.", "Open the calls' traces.",
                    f"/admin/calls?clinic={inc.clinic_id}")
        case "patients_cant_connect":
            return (f"{at}{_plural(inc.count, 'patient')} couldn't connect ({inc.subject}).",
                    "Check the call page, LiveKit and the worker.", None)
        case "server_error":
            return (f"Server error: {inc.subject}, {_plural(inc.count, 'time')}.",
                    "See the API log for the traceback.", None)
        case "livekit_minutes":
            return (f"LiveKit minutes: {inc.detail}.",
                    "Upgrade the LiveKit plan or self-host before calls are refused.", None)
        case "purge_failed":
            return ("Deleting expired transcripts failed.",
                    "Transcripts older than 30 days may still be stored: check the API log.", None)
    # The clinic-side problems read the same for the operator, with the clinic named.
    title, action, _ = clinic_words(inc, inc.clinic_id or 0)
    return (f"{at}{title}", action, f"/admin/clinics/{inc.clinic_id}" if inc.clinic_id else None)


def _problem(inc: repo.Incident, words: tuple[str, str, str | None], seen, clinic_name: str | None = None) -> schemas.Problem:
    title, action, link = words
    return schemas.Problem(
        id=inc.id, kind=inc.kind, severity=inc.severity, title=title, action=action, link=link,
        clinic_id=inc.clinic_id, clinic_name=clinic_name, count=inc.count,
        since=convert.utc(inc.opened_at), last_seen=convert.utc(inc.last_seen_at),
        resolved_at=convert.utc(inc.resolved_at), seen=seen is not None,
    )


def _split(problems: list[schemas.Problem]) -> schemas.Problems:
    open_ = sorted((p for p in problems if p.resolved_at is None), key=lambda p: (RANK[p.severity], -p.since.timestamp()))
    return schemas.Problems(open=open_, recent=[p for p in problems if p.resolved_at is not None])


@router.get("/api/clinics/{clinic_id}/problems", response_model=schemas.Problems)
def clinic_problems(request: Request, clinic_id: int = Depends(open_clinic)):
    with request.app.state.sessions() as s:
        rows = repo.list_incidents(s, since=utc_now() - HISTORY, clinic_id=clinic_id)
        return _split([
            _problem(i, clinic_words(i, clinic_id), i.seen_by_clinic_at)
            for i in rows if incidents.clinic_sees(i.kind)
        ])


@router.post("/api/clinics/{clinic_id}/problems/{problem_id}/seen", response_model=schemas.Problem)
def clinic_seen(problem_id: int, request: Request, clinic_id: int = Depends(open_clinic)):
    """Only the clinic's own problems: a system-wide one (receptionist
    offline) stays up until it's fixed."""
    with staff_errors(), request.app.state.sessions() as s:
        inc = repo.in_clinic(s, repo.Incident, problem_id, clinic_id)
        if not incidents.clinic_sees(inc.kind):
            raise repo.NotFound(problem_id)
        inc = repo.mark_incident_seen(s, inc.id, "clinic", utc_now())
        return _problem(inc, clinic_words(inc, clinic_id), inc.seen_by_clinic_at)


@router.get("/api/admin/problems", response_model=schemas.Problems)
def admin_problems(request: Request, _viewer: Viewer = Depends(admin)):
    with request.app.state.sessions() as s:
        names = {c.id: c.name for c in repo.list_clinics(s)}
        rows = repo.list_incidents(s, since=utc_now() - HISTORY)
        return _split([
            _problem(i, admin_words(i, names.get(i.clinic_id)), i.seen_by_admin_at, names.get(i.clinic_id))
            for i in rows
        ])


@router.post("/api/admin/problems/{problem_id}/seen", response_model=schemas.Problem)
def admin_seen(problem_id: int, request: Request, _viewer: Viewer = Depends(admin)):
    with staff_errors(), request.app.state.sessions() as s:
        inc = repo.mark_incident_seen(s, problem_id, "admin", utc_now())
        name = repo.get_clinic(s, inc.clinic_id).name if inc.clinic_id else None
        return _problem(inc, admin_words(inc, name), inc.seen_by_admin_at, name)
