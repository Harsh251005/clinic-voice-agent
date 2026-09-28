"""What counts as a problem, and when one opens and closes.

Two sorts of problem:
- conditions, re-checked every half minute by `sync` (the receptionist is
  offline, a clinic has no doctor with hours): open while true, closed the
  moment they aren't;
- events, reported as they happen by `report` (a patient's call page
  couldn't connect, a server error): counted while they keep coming, closed
  after a quiet spell.

Plain functions over a session, like booking.py. The words people read
live in the API (api/dashboard/problems.py); nothing here is patient data.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from clinic_agent import booking
from clinic_agent.context import clinic_now
from clinic_agent.store import repo
from clinic_agent.store.db import Session

logger = logging.getLogger("clinic-agent.incidents")


@dataclass(frozen=True)
class Kind:
    severity: str  # critical | warning | info
    clinic_sees: bool  # shown on the clinic's dashboard too (in plain words)
    quiet_minutes: int | None = None  # events: close after this long with no new report; None = a condition


KINDS = {
    "worker_offline": Kind("critical", clinic_sees=True),
    "vendor_errors": Kind("warning", clinic_sees=False),
    "calls_failing": Kind("warning", clinic_sees=True),
    "patients_cant_connect": Kind("warning", clinic_sees=True, quiet_minutes=120),
    "server_error": Kind("warning", clinic_sees=False, quiet_minutes=15),
    "no_doctors": Kind("warning", clinic_sees=True),
    "doctor_no_hours": Kind("warning", clinic_sees=True),
    "clinic_paused": Kind("info", clinic_sees=True),
    "bookings_need_call": Kind("warning", clinic_sees=True),
    "livekit_minutes": Kind("warning", clinic_sees=False),
    "purge_failed": Kind("warning", clinic_sees=False, quiet_minutes=24 * 60),
}

def clinic_sees(kind: str) -> bool:
    known = KINDS.get(kind)
    return bool(known and known.clinic_sees)


# Why a patient's call page gave up: fixed codes, never free text.
CONNECT_FAILURES = ("mic_blocked", "no_mic", "connect_failed", "no_answer", "dropped")

HEARTBEAT_STALE = timedelta(seconds=90)  # three missed beats
VENDOR_WINDOW, VENDOR_MIN_ERRORS = timedelta(minutes=15), 3
FAILING_WINDOW, FAILING_MIN_CALLS = timedelta(minutes=60), 2
DROPPED_GRACE = timedelta(minutes=2)  # past the time limit: the worker would have ended the call
LIVEKIT_FREE_MINUTES = 1_000  # LiveKit Cloud's free tier, agent-session minutes a month
LIVEKIT_WARN, LIVEKIT_CRITICAL = 0.8, 0.95
KEEP_RESOLVED = timedelta(days=90)


@dataclass(frozen=True)
class Finding:
    kind: str
    clinic_id: int | None = None
    subject: str = ""
    detail: str = ""
    severity: str | None = None  # None: the kind's own


def report(s: Session, kind: str, now: datetime, *, clinic_id: int | None = None, subject: str = "", detail: str = "") -> None:
    """Something just went wrong (an event): open its incident or count it."""
    repo.hold_incident(s, kind=kind, severity=KINDS[kind].severity, now=now,
                       clinic_id=clinic_id, subject=subject, detail=detail, bump=True)


def clear(s: Session, kind: str, now: datetime, *, clinic_id: int | None = None, subject: str = "") -> None:
    """The thing an event was about works again (the purge succeeded)."""
    key = repo.incident_key(kind, clinic_id, subject)
    for inc in repo.open_incidents(s):
        if inc.key == key:
            repo.resolve_incident(s, inc.id, now)


def sync(s: Session, now: datetime, *, max_call_minutes: int) -> None:
    """Re-check every condition; open, update and close incidents to match.
    `now` is naive UTC."""
    held = set()
    for f in findings(s, now, max_call_minutes=max_call_minutes):
        row = repo.hold_incident(s, kind=f.kind, severity=f.severity or KINDS[f.kind].severity, now=now,
                                 clinic_id=f.clinic_id, subject=f.subject, detail=f.detail)
        held.add(row.key)
    for inc in repo.open_incidents(s):
        kind = KINDS.get(inc.kind)
        if kind is None or kind.quiet_minutes is None:
            gone = inc.key not in held
        else:
            gone = now - inc.last_seen_at > timedelta(minutes=kind.quiet_minutes)
        if gone:
            repo.resolve_incident(s, inc.id, now)
    repo.prune_beats(s, now - timedelta(days=1))
    repo.delete_old_incidents(s, now - KEEP_RESOLVED)


def findings(s: Session, now: datetime, *, max_call_minutes: int) -> list[Finding]:
    """Every condition true right now."""
    out = [*_receptionist(s, now), *_vendors(s, now), *_minutes(s, now, max_call_minutes)]
    calls = repo.patient_calls_since(s, dropped_before(now, max_call_minutes) - FAILING_WINDOW)
    for clinic in repo.list_clinics(s):
        out += _setup(clinic)
        if clinic.active:
            out += _failing_calls(clinic.id, calls, now, max_call_minutes)
            out += _bookings_need_call(s, clinic)
    return out


def _receptionist(s: Session, now: datetime) -> list[Finding]:
    last = repo.last_beat(s)
    if last is not None and now - last <= HEARTBEAT_STALE:
        return []
    return [Finding("worker_offline", detail=f"{last:%Y-%m-%dT%H:%M:%SZ}" if last else "never")]


def _vendors(s: Session, now: datetime) -> list[Finding]:
    errors = [e for e, _stack, _clinic in repo.events_since(s, now - VENDOR_WINDOW, ["error"])]
    counts = Counter(e.name for e in errors)
    latest = {e.name: e.detail for e in errors}
    return [
        Finding("vendor_errors", subject=name, detail=f"{n} errors in 15 minutes; latest {latest[name]}")
        for name, n in counts.items() if n >= VENDOR_MIN_ERRORS
    ]


def _minutes(s: Session, now: datetime, max_call_minutes: int) -> list[Finding]:
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cap = timedelta(minutes=max_call_minutes)
    used = sum(
        (min((c.ended_at or now) - c.started_at, cap) for c in repo.patient_calls_since(s, month)),
        timedelta(),
    ).total_seconds() / 60
    share = used / LIVEKIT_FREE_MINUTES
    if share < LIVEKIT_WARN:
        return []
    return [Finding("livekit_minutes", detail=f"{used:.0f} of {LIVEKIT_FREE_MINUTES} minutes this month",
                    severity="critical" if share >= LIVEKIT_CRITICAL else "warning")]


def _setup(clinic) -> list[Finding]:
    if not clinic.active:
        return [Finding("clinic_paused", clinic.id)]
    doctors = [d for d in clinic.doctors if d.active]
    if not doctors:
        return [Finding("no_doctors", clinic.id)]
    return [Finding("doctor_no_hours", clinic.id, subject=str(d.id), detail=d.name) for d in doctors if not d.hours]


def _failing_calls(clinic_id: int, calls, now: datetime, max_call_minutes: int) -> list[Finding]:
    """Calls that went wrong in the last hour: failed, ended by an error, or
    dropped (never finished, and now past the time limit: the worker died)."""
    since = now - FAILING_WINDOW
    cutoff = dropped_before(now, max_call_minutes)

    def went_wrong(c) -> bool:
        if c.ended_at is None:
            return cutoff - FAILING_WINDOW <= c.started_at < cutoff
        return c.ended_at >= since and (c.outcome == "failed" or c.end_reason == "error")

    n = sum(1 for c in calls if c.clinic_id == clinic_id and went_wrong(c))
    return [Finding("calls_failing", clinic_id, detail=f"{n} calls in the last hour")] if n >= FAILING_MIN_CALLS else []


def dropped_before(now: datetime, max_call_minutes: int) -> datetime:
    """An unfinished call that started before this was dropped, as the admin panel counts it."""
    return now - timedelta(minutes=max_call_minutes) - DROPPED_GRACE


def _bookings_need_call(s: Session, clinic) -> list[Finding]:
    local = clinic_now(clinic.timezone)
    last = local.date() + timedelta(days=clinic.booking_window_days)
    appts = [a for a in repo.booked_between(s, clinic.id, local.date(), last) if a.starts_at >= local]
    if not appts:
        return []
    time_off = repo.time_off_overlapping(s, clinic.id, local.date(), last)
    n = sum(1 for a in appts if booking.appointment_problem(a, time_off))
    return [Finding("bookings_need_call", clinic.id, detail=str(n))] if n else []
