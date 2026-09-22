"""Database rows → API shapes."""

from __future__ import annotations

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
