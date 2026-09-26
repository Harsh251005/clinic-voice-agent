"""Database rows → API shapes."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from api.dashboard import schemas
from clinic_agent.prompts import weekly_hours


def sittings(hours) -> list[schemas.Sitting]:
    return [schemas.Sitting(weekday=h.weekday, start=h.start, end=h.end)
            for h in sorted(hours, key=lambda h: (h.weekday, h.start))]


def hours_text(items: list[schemas.Sitting]) -> str:
    """The receptionist's own description (prompts.weekly_hours), so the
    dashboard preview can never disagree with what callers hear."""
    return weekly_hours(SimpleNamespace(hours=items))


def doctor(d, upcoming: int) -> schemas.Doctor:
    hours = sittings(d.hours)
    return schemas.Doctor(
        id=d.id, name=d.name, specialty=d.specialty, fee=d.fee, slot_minutes=d.slot_minutes,
        active=d.active, hours=hours, hours_text=hours_text(hours), upcoming=upcoming,
    )


def clinic(c, time_off, upcoming: dict[int, int], public_base_url: str) -> schemas.Clinic:
    return schemas.Clinic(
        id=c.id, name=c.name, slug=c.slug, call_link=f"{public_base_url}/call/{c.slug}",
        address=c.address, phone=c.phone, timezone=c.timezone,
        booking_window_days=c.booking_window_days, slots_offered=c.slots_offered,
        doctors=[doctor(d, upcoming.get(d.id, 0)) for d in c.doctors],
        faq=[schemas.Faq(id=f.id, question=f.question, answer=f.answer) for f in c.faq],
        time_off=[schemas.TimeOff(id=t.id, date_from=t.date_from, date_to=t.date_to,
                                  doctor_id=t.doctor_id, reason=t.reason) for t in time_off],
    )


def appointment(a, problem: str | None = None) -> schemas.Appointment:
    return schemas.Appointment(
        id=a.id, doctor_id=a.doctor_id, doctor_name=a.doctor.name,
        patient_name=a.patient.name, patient_phone=a.patient.phone,
        starts_at=a.starts_at, ends_at=a.ends_at, status=a.status, source=a.source,
        reason=a.reason, problem=problem,
    )


# ---------- calls ----------

def utc(at: datetime | None) -> datetime | None:
    """Stored naive UTC → aware, so the browser shows it in local time."""
    return at.replace(tzinfo=UTC) if at else None


def call_status(call, dropped_before: datetime) -> str:
    """dropped_before: an unfinished call older than this was never finished
    (the time limit would have ended it), so the worker died mid-call."""
    if call.ended_at is not None:
        return "ended"
    return "dropped" if call.started_at < dropped_before else "live"


def call_summary(call, clinic_name: str, events, dropped_before: datetime) -> schemas.CallSummary:
    return schemas.CallSummary(
        id=call.id, clinic_id=call.clinic_id, clinic_name=clinic_name, started_at=utc(call.started_at),
        duration_s=round((call.ended_at - call.started_at).total_seconds()) if call.ended_at else None,
        status=call_status(call, dropped_before), end_reason=call.end_reason, outcome=call.outcome,
        stack=call.stack, turn_count=call.turn_count, error_count=call.error_count,
        tool_failures=sum(1 for e in events if e.kind == "tool" and not e.ok),
        appointments=[schemas.CallChange(**c) for c in call.appointments],
    )


def trace_event(e) -> schemas.TraceEvent:
    return schemas.TraceEvent(t_ms=e.t_ms, kind=e.kind, name=e.name, duration_ms=e.duration_ms, ok=e.ok, detail=e.detail)


def transcript(items: list[dict]) -> list[schemas.TranscriptItem]:
    return [schemas.TranscriptItem(**i) for i in items]


def access(a) -> schemas.TranscriptAccess:
    return schemas.TranscriptAccess(email=a.email, reason=a.reason, at=utc(a.at))
