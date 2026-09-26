"""The operator's panel (/api/admin): is the receptionist working, for every
clinic? Call traces, errors, vendor latency, and adding, pausing or deleting
clinics. Admins only.

Nothing here returns patient data. Traces hold no words from calls; the one
exception is a call's transcript, which an admin reads only by giving a
reason first. The reason is logged and the clinic sees it (A4).
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dashboard import convert, schemas
from api.dashboard.access import Viewer, admin, staff_errors
from clinic_agent.store import repo
from clinic_agent.store.models import utc_now

router = APIRouter(prefix="/api/admin")

STAGES = ("stt", "eou", "llm", "tts", "reply")
QUIET_AFTER = timedelta(days=3)  # an active clinic with no calls for this long is worth a look
DROPPED_GRACE = timedelta(minutes=2)  # past the time limit: the worker would have ended it


def dropped_before(request: Request, now: datetime) -> datetime:
    return now - timedelta(minutes=request.app.state.cfg.max_call_minutes) - DROPPED_GRACE


def _summaries(s, calls, request: Request) -> list[schemas.CallSummary]:
    names = {c.id: c.name for c in repo.list_clinics(s)}
    events = defaultdict(list)
    for e in repo.call_events(s, [c.id for c in calls]):
        events[e.call_id].append(e)
    cutoff = dropped_before(request, utc_now())
    return [convert.call_summary(c, names.get(c.clinic_id, "?"), events[c.id], cutoff) for c in calls]


# ---------- calls ----------

@router.get("/calls", response_model=list[schemas.CallSummary], dependencies=[Depends(admin)])
def calls(
    request: Request,
    clinic_id: int | None = None,
    outcome: str | None = None,
    status: str | None = None,  # "dropped" only; the rest filter by outcome
    with_errors: bool = False,
    before_id: int | None = None,
):
    with request.app.state.sessions() as s:
        found = repo.list_calls(
            s, clinic_id=clinic_id, outcome=outcome, with_errors=with_errors, before_id=before_id,
            open_before=dropped_before(request, utc_now()) if status == "dropped" else None,
        )
        return _summaries(s, found, request)


@router.get("/calls/{call_id}", response_model=schemas.CallTrace, dependencies=[Depends(admin)])
def call_trace(call_id: int, request: Request):
    with staff_errors(), request.app.state.sessions() as s:
        call = repo.get_call(s, call_id)
        (summary,) = _summaries(s, [call], request)
        return schemas.CallTrace(
            **summary.model_dump(),
            events=[convert.trace_event(e) for e in repo.call_events(s, [call.id])],
            transcript_kept=repo.has_transcript(s, call.id),
            accesses=[convert.access(a) for a in repo.transcript_accesses(s, call.id)],
        )


@router.post("/calls/{call_id}/transcript", response_model=list[schemas.TranscriptItem])
def open_transcript(call_id: int, body: schemas.TranscriptReason, request: Request, viewer: Viewer = Depends(admin)):
    """Break-glass: the reason is logged (and shown to the clinic) before
    the words are returned."""
    with staff_errors(), request.app.state.sessions() as s:
        if not repo.has_transcript(s, call_id):
            repo.get_call(s, call_id)  # 404 for no such call
            raise HTTPException(404, "This call's transcript was deleted after 30 days.")
        repo.log_transcript_access(s, call_id, viewer.email or "(sign-in off)", body.reason.strip())
        return convert.transcript(repo.get_transcript(s, call_id).items)


# ---------- health ----------

def _n(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def percentile(values: list[int], p: float) -> int:
    """Nearest-rank percentile of a non-empty list."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


@router.get("/health", response_model=schemas.Health, dependencies=[Depends(admin)])
def health(request: Request, days: int = 7):
    days = max(1, min(days, 90))
    now = utc_now()
    since = now - timedelta(days=days)
    with request.app.state.sessions() as s:
        recent = repo.list_calls(s, since=since, limit=100_000)
        stage_rows = repo.events_since(s, since, STAGES)
        error_rows = repo.events_since(s, since, ["error"])
        clinics = repo.list_clinics(s)
        counts = repo.call_counts(s, since)
    cutoff = dropped_before(request, now)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    outcomes: dict[str, int] = defaultdict(int)
    dropped = []
    for c in recent:
        status = convert.call_status(c, cutoff)
        if status == "dropped":
            dropped.append(c)
        elif status == "ended":
            outcomes[c.outcome] += 1

    samples: dict[tuple[str, str], list[int]] = defaultdict(list)
    for e, stack, _ in stage_rows:
        if e.duration_ms is not None:
            samples[(e.kind, stack)].append(e.duration_ms)
    stages = [
        schemas.Stage(stage=stage, stack=stack, count=len(v), p50_ms=percentile(v, 50), p95_ms=percentile(v, 95))
        for (stage, stack), v in sorted(samples.items(), key=lambda kv: (STAGES.index(kv[0][0]), kv[0][1]))
    ]

    errors: dict[str, list] = defaultdict(list)
    for e, _, _ in error_rows:
        errors[e.name].append(e.call_id)
    vendors = [schemas.VendorErrors(name=n, errors=len(ids), calls=len(set(ids)))
               for n, ids in sorted(errors.items(), key=lambda kv: -len(kv[1]))]

    names = {c.id: c.name for c in clinics}
    attention = [
        schemas.Attention(kind="dropped", call_id=c.id, clinic_id=c.clinic_id,
                          text=f"A call to {names.get(c.clinic_id, '?')} never finished: the worker may have stopped mid-call.")
        for c in dropped[:10]
    ] + [
        schemas.Attention(kind="failed", call_id=c.id, clinic_id=c.clinic_id,
                          text=f"A call to {names.get(c.clinic_id, '?')} ended on an error.")
        for c in recent if c.outcome == "failed"
    ][:10]
    attention += [
        schemas.Attention(kind="errors", text=f"{v.name}: {_n(v.errors, 'error')} in {_n(v.calls, 'call')}.")
        for v in vendors if v.errors
    ]
    for clinic in clinics:
        last = counts.get(clinic.id, (0, 0, None))[2]
        if clinic.active and last is not None and now - last > QUIET_AFTER:
            attention.append(schemas.Attention(
                kind="quiet", clinic_id=clinic.id,
                text=f"{clinic.name} has had no calls for {(now - last).days} days."))

    return schemas.Health(
        days=days, calls=len(recent), calls_today=sum(1 for c in recent if c.started_at >= today),
        outcomes=dict(outcomes), dropped=len(dropped), with_errors=sum(1 for c in recent if c.error_count),
        stages=stages, vendors=vendors, attention=attention,
    )


@router.get("/errors", response_model=list[schemas.ErrorGroup], dependencies=[Depends(admin)])
def error_groups(request: Request, days: int = 7):
    since = utc_now() - timedelta(days=max(1, min(days, 90)))
    with request.app.state.sessions() as s:
        rows = repo.events_since(s, since, ["error"])
        started = {c.id: c.started_at for c in repo.list_calls(s, since=since, limit=100_000)}
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for e, _, _ in rows:
        groups[(e.name, e.detail)].append(e.call_id)
    out = []
    for (name, detail), ids in groups.items():
        newest = sorted(set(ids), reverse=True)
        out.append(schemas.ErrorGroup(
            name=name, detail=detail, count=len(ids), call_ids=newest[:5],
            last_at=convert.utc(max(started[i] for i in newest if i in started)),
        ))
    return sorted(out, key=lambda g: g.last_at, reverse=True)


# ---------- clinics ----------

def _admin_clinics(s) -> list[schemas.AdminClinic]:
    counts = repo.call_counts(s, utc_now() - timedelta(days=7))
    out = []
    for c in repo.list_clinics(s):
        calls_7d, errors_7d, last = counts.get(c.id, (0, 0, None))
        out.append(schemas.AdminClinic(
            id=c.id, name=c.name, slug=c.slug, active=c.active,
            doctors=sum(1 for d in repo.get_clinic(s, c.id).doctors if d.active),
            members=[schemas.Member(id=m.id, email=m.email) for m in repo.list_members(s, c.id)],
            calls_7d=calls_7d, calls_with_errors_7d=errors_7d, last_call_at=convert.utc(last),
        ))
    return out


@router.get("/clinics", response_model=list[schemas.AdminClinic], dependencies=[Depends(admin)])
def clinics(request: Request):
    with request.app.state.sessions() as s:
        return _admin_clinics(s)


@router.put("/clinics/{clinic_id}/active", response_model=schemas.AdminClinic, dependencies=[Depends(admin)])
def set_active(clinic_id: int, body: schemas.ActiveIn, request: Request):
    with staff_errors(), request.app.state.sessions() as s:
        repo.set_clinic_active(s, clinic_id, body.active)
        return next(c for c in _admin_clinics(s) if c.id == clinic_id)


@router.delete("/clinics/{clinic_id}", dependencies=[Depends(admin)])
def delete_clinic(clinic_id: int, body: schemas.DeleteClinicIn, request: Request) -> dict:
    """Irreversible: the clinic must be paused first, and its exact name typed."""
    with staff_errors(), request.app.state.sessions() as s:
        clinic = repo.get_clinic(s, clinic_id)
        if clinic.active:
            raise HTTPException(422, "Pause the clinic before deleting it.")
        if body.confirm_name.strip() != clinic.name:
            raise HTTPException(422, "Type the clinic's name exactly to delete it.")
        repo.delete_clinic(s, clinic_id)
    return {"ok": True}
