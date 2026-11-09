"""What counts as a problem, and when one opens and closes.

Two sorts of problem:
- conditions, re-checked every half minute by `sync` (the receptionist is
  offline, a clinic has no doctor with hours): open while true, closed the
  moment they aren't;
- events, reported as they happen by `report` (a patient's call page
  couldn't connect, a server error): counted while they keep coming.

A problem closes on proof that it is fixed (Harsh, 2026-11-09), never on a
timer alone: a vendor that failed closes once a later call shows it working,
failed calls once the clinic's next call ends well, a patient who couldn't
connect once a call next connects there, and the rest on their own next
success (`clear`). Only what nothing retries closes after a quiet spell, and
it is marked so ("quiet": last happened then, not tried again since).

Plain functions over a session, like booking.py. The words people read
live in the API (api/dashboard/problems.py); nothing here is patient data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from clinic_agent import booking, costs
from clinic_agent.context import clinic_now
from clinic_agent.dispatch import LANGUAGES
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
    "language_off": Kind("critical", clinic_sees=True),  # the only line: no calls at all
    # Clinics see it too, in plain words (Harsh, 2026-11-09): their calls are the ones affected.
    "vendor_errors": Kind("warning", clinic_sees=True),
    "calls_failing": Kind("warning", clinic_sees=True),
    "patients_cant_connect": Kind("warning", clinic_sees=True, quiet_minutes=120),
    "server_error": Kind("warning", clinic_sees=False, quiet_minutes=15),
    "no_doctors": Kind("warning", clinic_sees=True),
    "doctor_no_hours": Kind("warning", clinic_sees=True),
    "clinic_paused": Kind("info", clinic_sees=True),
    "bookings_need_call": Kind("warning", clinic_sees=True),
    "livekit_minutes": Kind("warning", clinic_sees=False),
    "purge_failed": Kind("warning", clinic_sees=False, quiet_minutes=24 * 60),
    "hindi_names_failing": Kind("warning", clinic_sees=False, quiet_minutes=60),
    "price_missing": Kind("warning", clinic_sees=False),
    # An admin's Record click failed; calls say the phrase live meanwhile.
    "voice_clip_failed": Kind("warning", clinic_sees=False, quiet_minutes=24 * 60),
    # The admin's English phrase could not be turned into Hindi (OpenAI).
    "phrase_translation_failing": Kind("warning", clinic_sees=False, quiet_minutes=60),
    # A call could not read its phrases or recordings; it said them all live.
    "voice_clips_unread": Kind("warning", clinic_sees=False, quiet_minutes=60),
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
LIVEKIT_FREE_MINUTES = 1_000  # LiveKit Cloud's free tier, when no allowance is set in the admin panel
LIVEKIT_WARN, LIVEKIT_CRITICAL = 0.8, 0.95
KEEP_RESOLVED = timedelta(days=90)
PRICED_WINDOW = timedelta(days=35)  # usage this recent must have a price (this month and the last)


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


def clear(s: Session, kind: str, now: datetime, *, clinic_id: int | None = None, subject: str | None = "") -> None:
    """The thing an event was about works again (the purge succeeded): its
    problem closes as fixed. `subject=None` closes every subject of the kind
    (for that clinic, when given)."""
    for inc in repo.open_incidents(s):
        if inc.kind != kind or inc.clinic_id != clinic_id:
            continue
        if subject is None or inc.key == repo.incident_key(kind, clinic_id, subject):
            repo.resolve_incident(s, inc.id, now, how="fixed")


def route_of(subject: str) -> str:
    """A server error's route ("GET /api/x" of "GET /api/x · KeyError")."""
    return subject.split(" · ", 1)[0]


def failing_routes(s: Session) -> set[str]:
    """Routes with an open server error, so the API can tell when one works again."""
    return {route_of(i.subject) for i in repo.open_incidents(s) if i.kind == "server_error"}


def route_works(s: Session, route: str, now: datetime) -> None:
    """That route just answered without a server error: its problems close as fixed."""
    for inc in repo.open_incidents(s):
        if inc.kind == "server_error" and route_of(inc.subject) == route:
            repo.resolve_incident(s, inc.id, now, how="fixed")


def sync(s: Session, now: datetime, *, max_call_minutes: int) -> None:
    """Re-check every condition; open, update and close incidents to match.
    `now` is naive UTC."""
    held = set()
    for f in findings(s, now, max_call_minutes=max_call_minutes):
        row = repo.hold_incident(s, kind=f.kind, severity=f.severity or KINDS[f.kind].severity, now=now,
                                 clinic_id=f.clinic_id, subject=f.subject, detail=f.detail)
        held.add(row.key)
    connected = _connected_since(s, now)
    for inc in repo.open_incidents(s):
        kind = KINDS.get(inc.kind)
        if kind is None or kind.quiet_minutes is None:
            if inc.key not in held:
                repo.resolve_incident(s, inc.id, now, how="fixed")
        elif inc.kind == "patients_cant_connect" and connected.get(inc.clinic_id, inc.last_seen_at) > inc.last_seen_at:
            repo.resolve_incident(s, inc.id, now, how="fixed")  # a call connected there since
        elif now - inc.last_seen_at > timedelta(minutes=kind.quiet_minutes):
            repo.resolve_incident(s, inc.id, now, how="quiet")
    repo.prune_beats(s, now - timedelta(days=1))
    repo.delete_old_incidents(s, now - KEEP_RESOLVED)


def findings(s: Session, now: datetime, *, max_call_minutes: int) -> list[Finding]:
    """Every condition true right now."""
    out = [*_receptionist(s, now), *_vendors(s, now), *_minutes(s, now, max_call_minutes), *_unpriced(s, now)]
    calls = repo.patient_calls_since(s, dropped_before(now, max_call_minutes) - FAILING_WINDOW, with_tests=True)
    for clinic in repo.list_clinics(s):
        out += _setup(clinic)
        if clinic.active:
            out += _failing_calls(clinic.id, calls, now, max_call_minutes, clinic.timezone)
            out += _bookings_need_call(s, clinic)
    return out


def _receptionist(s: Session, now: datetime) -> list[Finding]:
    last = repo.last_beat(s)
    if last is not None and now - last <= HEARTBEAT_STALE:
        # Up, but a line whose keys are missing isn't offered to callers.
        live = repo.live_languages(s, now - HEARTBEAT_STALE) or set()
        return [Finding("language_off", subject=lang) for lang in LANGUAGES if lang not in live]
    return [Finding("worker_offline", detail=f"{last:%Y-%m-%dT%H:%M:%SZ}" if last else "never")]


PARTS = {3: ("stt", "llm", "tts"), 2: ("text", "llm")}  # a call's stack, in order (call_record.stack_of)


def _model(name: str) -> str:
    """"sarvam/bulbul:v3" -> "bulbul:v3": an error names its source by the
    plugin's provider, the stack by the line's vendor; the model is in both."""
    return name.split("/", 1)[-1]


def _vendors(s: Session, now: datetime) -> list[Finding]:
    """A vendor with 3+ errors in 15 minutes, counting only errors after the
    last call that shows it working (it did its part with no error from it):
    once it works again, the problem closes."""
    calls = {c.id: c for c in repo.calls_started_since(s, now - VENDOR_WINDOW)}
    errors: list[tuple[datetime, str, str]] = []  # (when, name, detail)
    erred: dict[int, set[str]] = {}  # call id -> models that failed on it
    did: dict[int, set[str]] = {}  # call id -> parts it did (stt, llm, tts)
    for e, _stack, _clinic in repo.events_since(s, now - VENDOR_WINDOW, ["error", "stt", "llm", "tts"]):
        call = calls.get(e.call_id)
        if call is None:
            continue
        if e.kind == "error":
            errors.append((call.started_at + timedelta(milliseconds=e.t_ms), e.name, e.detail))
            erred.setdefault(call.id, set()).add(_model(e.name))
        else:
            did.setdefault(call.id, set()).add(e.kind)
    out = []
    for name in {n for _, n, _ in errors}:
        model = _model(name)
        worked = [c.started_at for c in calls.values() if c.ended_at and model not in erred.get(c.id, ())
                  and _part(c.stack, model) in did.get(c.id, ())]
        since = max(worked, default=None)
        mine = sorted((at, d) for at, n, d in errors if n == name and (since is None or at > since))
        if len(mine) >= VENDOR_MIN_ERRORS:
            part = next((p for c in calls.values() if (p := _part(c.stack, model))), "")
            out.append(Finding("vendor_errors", subject=name, detail=vendor_detail(part, len(mine), mine[-1][1])))
    return out


def vendor_detail(part: str, count: int, latest: str) -> str:
    """"tts|3|APIStatusError 402, fatal": which part of the call, how many
    errors in the window, the latest one. Read back by `parse_vendor_detail`."""
    return f"{part}|{count}|{latest}"


def parse_vendor_detail(detail: str) -> tuple[str, int, str]:
    """(part, count, latest error); an older free-text detail reads as unknown."""
    part, _, rest = detail.partition("|")
    count, _, latest = rest.partition("|")
    if not count.isdigit():
        return "", 0, detail
    return part, int(count), latest


def _part(stack: str, model: str) -> str | None:
    """Which part of the call (stt, llm, tts) `model` played in its stack."""
    parts = stack.split(" · ")
    names = PARTS.get(len(parts), ())
    return next((names[i] for i, p in enumerate(parts) if i < len(names) and _model(p) == model), None)


def _connected_since(s: Session, now: datetime) -> dict[int, datetime]:
    """Each clinic's latest call start in the last day: a call connected then."""
    latest: dict[int, datetime] = {}
    for c in repo.calls_started_since(s, now - timedelta(days=1)):
        if c.started_at > latest.get(c.clinic_id, datetime.min):
            latest[c.clinic_id] = c.started_at
    return latest


def _minutes(s: Session, now: datetime, max_call_minutes: int) -> list[Finding]:
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cap = timedelta(minutes=max_call_minutes)
    used = sum(
        (min((c.ended_at or now) - c.started_at, cap) for c in repo.patient_calls_since(s, month, with_tests=True)),
        timedelta(),
    ).total_seconds() / 60
    free = _livekit_allowance(s, now)
    share = used / free if free else 0
    if share < LIVEKIT_WARN:
        return []
    return [Finding("livekit_minutes", detail=f"{used:.0f} of {free:.0f} minutes this month",
                    severity="critical" if share >= LIVEKIT_CRITICAL else "warning")]


def _livekit_allowance(s: Session, now: datetime) -> float:
    """The plan's free minutes as set in the admin panel (Costs, Prices)."""
    rows = [a for a in repo.cost_rows(s, "allowances")
            if a.provider == "livekit" and a.unit == "minutes" and a.valid_from <= now.date()]
    return rows[-1].quantity if rows else LIVEKIT_FREE_MINUTES  # sorted by valid_from


def _unpriced(s: Session, now: datetime) -> list[Finding]:
    """Recent usage the price list can't price: a model with no price on
    that day, or a dollar price with no rate. Its calls' costs show as
    incomplete until it is added."""
    book = costs.PriceBook(repo.cost_rows(s, "prices"), repo.cost_rows(s, "rates"))
    missing: dict[str, str] = {}
    for u in repo.usage_between(s, now - PRICED_WINDOW, now + timedelta(days=1)):
        p = book.priced(u)
        if p.missing == "rate":
            missing["rate"] = f"{u.at:%Y-%m-%d}"
        elif p.missing:
            missing.setdefault(f"{u.provider}/{u.model or '*'}/{u.unit}", f"{u.at:%Y-%m-%d}")
    return [Finding("price_missing", subject=subject, detail=since) for subject, since in missing.items()]


def _setup(clinic) -> list[Finding]:
    if not clinic.active:
        return [Finding("clinic_paused", clinic.id)]
    doctors = [d for d in clinic.doctors if d.active]
    if not doctors:
        return [Finding("no_doctors", clinic.id)]
    return [Finding("doctor_no_hours", clinic.id, subject=str(d.id), detail=d.name) for d in doctors if not d.hours]


def _failing_calls(clinic_id: int, calls, now: datetime, max_call_minutes: int, timezone: str = "Asia/Kolkata") -> list[Finding]:
    """Calls that went wrong in the last hour: failed, ended by an error, or
    dropped (never finished, and now past the time limit: the worker died).
    Only those after the clinic's last call that ended well count: one good
    call (a staff test call too) shows calls work again. `calls` include
    staff test calls; only patients' calls count as failures."""
    since = now - FAILING_WINDOW
    cutoff = dropped_before(now, max_call_minutes)
    mine = [c for c in calls if c.clinic_id == clinic_id]

    def went_wrong(c) -> bool:
        if c.test:
            return False
        if c.ended_at is None:
            return cutoff - FAILING_WINDOW <= c.started_at < cutoff
        return c.ended_at >= since and (c.outcome == "failed" or c.end_reason == "error")

    good = [c.started_at for c in mine if c.ended_at and c.outcome != "failed" and c.end_reason != "error"]
    last_good = max(good, default=None)
    bad = sorted(c.started_at for c in mine if went_wrong(c) and (last_good is None or c.started_at > last_good))
    if len(bad) < FAILING_MIN_CALLS:
        return []
    # When they started, in the clinic's own time ("3:12 PM"), so staff know whom to ring back.
    zone = ZoneInfo(timezone)
    times = [at.replace(tzinfo=UTC).astimezone(zone).strftime("%I:%M %p").lstrip("0") for at in bad]
    return [Finding("calls_failing", clinic_id, detail=f"{len(bad)}|{','.join(times)}"[:300])]


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
