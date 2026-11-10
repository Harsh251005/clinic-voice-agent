"""A busy fictional clinic, to see the dashboard the way a full practice does:
four doctors, a month of nearly full diaries behind and ten days ahead, and
about 500 calls. Its own clinic ("Busy Demo Clinic"), so it sits beside real
clinics without touching them, and deleting it (Admin, Clinics) removes all
of it. Run it again any time to get it back.

    uv run python -m seeds.busy_clinic                       # add it to the DATABASE_URL database
    uv run python -m seeds.busy_clinic --replace             # delete it and seed it fresh
    uv run python -m seeds.busy_clinic --member you@x.com    # also let that Google account open it

Fictional people only. Calls no vendor (the Hindi names are written here)
and records no usage, so the Costs page shows nothing for it: a call's
usage outlives its clinic, and made-up rupees would stay for good. The same
run on the same day gives the same clinic (a fixed random seed).
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from clinic_agent.context import clinic_now
from clinic_agent.store import repo
from clinic_agent.store.db import Session
from clinic_agent.store.models import utc_now
from clinic_agent.store.purge import transcript_expiry

NAME, SLUG = "Busy Demo Clinic", "busy-demo-clinic"
DAYS_BACK, DAYS_AHEAD = 30, 10
CALLS = 500
QUIET_HOURS = 3  # no failed or dropped call this recent: nothing here raises a live "calls failing" alarm
STACK = "sarvam/saaras:v3 · sarvam/sarvam-105b-conversations · sarvam/bulbul:v3"

MON_TO_SAT = range(6)
DOCTORS = [  # (name, Hindi name, specialty, fee, minutes per patient, sittings)
    ("Dr. Meera Kulkarni", "डॉक्टर मीरा कुलकर्णी", "General Physician", 500, 10,
     [(d, time(9, 30), time(13, 0)) for d in MON_TO_SAT] + [(d, time(17, 0), time(21, 0)) for d in MON_TO_SAT]),
    ("Dr. Sameer Khan", "डॉक्टर समीर ख़ान", "Paediatrician", 700, 15,
     [(d, time(10, 0), time(13, 30)) for d in MON_TO_SAT] + [(d, time(18, 0), time(20, 30)) for d in (0, 2, 4)]),
    ("Dr. Anjali Deshpande", "डॉक्टर अंजलि देशपांडे", "Gynaecologist", 900, 20,
     [(d, time(11, 0), time(14, 0)) for d in (0, 1, 3, 4)] + [(5, time(10, 0), time(13, 0))]),
    ("Dr. Vivek Reddy", "डॉक्टर विवेक रेड्डी", "Orthopaedic Surgeon", 1000, 15,
     [(d, time(17, 30), time(20, 30)) for d in (1, 3, 5)] + [(6, time(10, 0), time(12, 0))]),
]
REASONS = {
    "General Physician": ["Fever for 2 days", "Cough and cold", "BP check", "Diabetes review", "Stomach pain", "Headache", "Follow-up", ""],
    "Paediatrician": ["Vaccination", "Fever", "Ear pain", "Cough", "Not eating well", "Follow-up", ""],
    "Gynaecologist": ["Pregnancy check-up", "Irregular periods", "Follow-up", "Scan report", ""],
    "Orthopaedic Surgeon": ["Knee pain", "Back pain", "Shoulder pain", "Fracture follow-up", "Neck pain", ""],
}
FIRST = ["Aarav", "Riya", "Kavita", "Suresh", "Neha", "Farhan", "Priya", "Deepak", "Ananya", "Vikram", "Sunita", "Rahul",
         "Pooja", "Imran", "Sneha", "Manoj", "Divya", "Rohit", "Fatima", "Ganesh", "Shreya", "Nitin", "Asha", "Karan",
         "Meenal", "Yusuf", "Lata", "Harish", "Tanvi", "Omkar", "Zoya", "Prakash", "Nandini", "Ajay", "Rekha", "Tushar"]
LAST = ["Sharma", "Patil", "Shaikh", "Nair", "Joshi", "Iyer", "Desai", "Verma", "Gupta", "Menon", "Shah", "Singh",
        "Pawar", "Khan", "Rao", "Kapoor", "Bhosale", "Fernandes", "Mishra", "Chavan", "Thakur", "Sawant", "Pillai", "Gaikwad"]
FAQ = [
    ("Is there parking?", "Two-wheeler parking in front; cars can park on the lane behind the building."),
    ("How can I pay?", "Cash, UPI and cards are accepted."),
    ("Do you take walk-ins?", "Yes, but patients with an appointment are seen first."),
    ("Is there a lift?", "Yes, the clinic is on the first floor and there is a lift."),
    ("Do you do blood tests?", "Samples are collected at the clinic from 8 to 10 in the morning."),
    ("Is the clinic open on Sunday?", "Only the orthopaedic doctor sits on Sunday morning."),
]
GREETING = "नमस्ते, बिज़ी डेमो क्लिनिक में आपका स्वागत है। बताइए, मैं आपकी क्या मदद कर सकती हूँ?"


def seed_busy(s: Session, member: str = "") -> int:
    """Create the clinic with all its history and return its id."""
    rng = random.Random(7)
    clinic = repo.create_clinic(
        s, name=NAME, slug=SLUG, name_hi="बिज़ी डेमो क्लिनिक",
        address="2nd Floor, Lotus Arcade, S.V. Road, Borivali West, Mumbai", phone="02228901234",
        directions="Opposite the Borivali West bus depot, above the medical store.",
    )
    doctors = []
    for name, name_hi, specialty, fee, minutes, sittings in DOCTORS:
        d = repo.add_doctor(s, clinic.id, name=name, name_hi=name_hi, specialty=specialty, fee=fee, slot_minutes=minutes)
        repo.set_doctor_hours(s, d.id, sittings)
        doctors.append((d, sittings))
    for q, a in FAQ:
        repo.add_faq(s, clinic.id, q, a)
    if member:
        repo.add_member(s, clinic.id, member)

    now = clinic_now(clinic.timezone)
    today = now.date()
    repo.add_time_off(s, clinic.id, today + timedelta(days=4), today + timedelta(days=6),
                      doctor_id=doctors[2][0].id, reason="Conference")
    repo.add_time_off(s, clinic.id, today + timedelta(days=8), today + timedelta(days=8), reason="Clinic holiday")

    by_voice = _diaries(s, rng, clinic.id, doctors, now, repo.time_off_overlapping(
        s, clinic.id, today, today + timedelta(days=DAYS_AHEAD)))
    _calls(s, rng, clinic.id, by_voice, now)
    return clinic.id


def _person(rng: random.Random) -> tuple[str, str]:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}", f"9{rng.randrange(700_000_000, 999_999_999)}"


def _diaries(s: Session, rng: random.Random, clinic_id: int, doctors, now: datetime, time_off: list) -> list:
    """Each doctor's days, mostly full: past visits marked, a few cancelled,
    a few for the clinic to check. Returns the bookings calls made."""
    by_voice = []
    for offset in range(-DAYS_BACK, DAYS_AHEAD + 1):
        day = now.date() + timedelta(days=offset)
        fill = 0.85 if offset <= 1 else max(0.2, 0.75 - 0.06 * offset)  # the diary thins out further ahead
        for doctor, sittings in doctors:
            # Leave or a holiday that day: only a booking or two made before it was known,
            # so "bookings to call" shows on Today without drowning it.
            away = any(o.date_from <= day <= o.date_to and o.doctor_id in (None, doctor.id) for o in time_off)
            for weekday, start, end in sittings:
                if weekday != day.weekday():
                    continue
                at, stop = datetime.combine(day, start), datetime.combine(day, end)
                while at + timedelta(minutes=doctor.slot_minutes) <= stop:
                    if rng.random() < (0.04 if away else fill):
                        by_voice.extend(_book(s, rng, clinic_id, doctor, at, now))
                    at += timedelta(minutes=doctor.slot_minutes)
    return by_voice


def _book(s: Session, rng: random.Random, clinic_id: int, doctor, at: datetime, now: datetime) -> list:
    name, phone = _person(rng)
    voice = rng.random() < 0.7
    reason = rng.choice(REASONS[doctor.specialty])
    try:
        a = repo.book(s, clinic_id, doctor.id, at, name, phone, source="voice" if voice else "dashboard",
                      reason=reason, reason_unsure=voice and bool(reason) and at > now and rng.random() < 0.04)
    except repo.SlotTaken:
        return []
    roll = rng.random()
    if roll < 0.05:
        repo.cancel_appointment(s, a.id)
    elif a.ends_at <= now:
        repo.set_visit(s, a.id, "no_show" if roll < 0.15 else "done")
    elif a.starts_at <= now:
        repo.set_visit(s, a.id, "arrived")
    return [a] if voice else []  # cancelled ones too: a call cancelled them


def _ev(t: int, kind: str, ms: int | None, name: str = "", ok: bool = True, detail: str = "") -> dict:
    return {"t_ms": t, "kind": kind, "name": name, "duration_ms": ms, "ok": ok, "detail": detail}


def _turn(rng: random.Random, t: int) -> list[dict]:
    return [_ev(t, "stt", rng.randrange(150, 450)), _ev(t, "eou", rng.randrange(200, 700)),
            _ev(t + 400, "llm", rng.randrange(400, 1400)), _ev(t + 500, "tts", rng.randrange(180, 420)),
            _ev(t + 500, "reply", rng.randrange(900, 2600))]


def _calls(s: Session, rng: random.Random, clinic_id: int, by_voice: list, now: datetime) -> None:
    """About CALLS calls over the same month, in clinic hours: most book,
    many only ask, a few fail or drop. A booking call comes a day or two
    before the visit it booked; a cancelling one points at a cancelled visit."""
    utc, offset = utc_now(), now.replace(tzinfo=None) - utc_now()  # clinic-local minus UTC
    oldest = utc - timedelta(days=DAYS_BACK)
    booked = [a for a in by_voice if a.status == "booked"]
    cancelled = [a for a in by_voice if a.status != "booked"]
    rng.shuffle(booked)

    def any_time() -> datetime:
        """A moment in the last month, between 8 in the morning and 10 at night at the clinic."""
        day = now.date() - timedelta(days=rng.randrange(DAYS_BACK))
        local = datetime.combine(day, time(8, 0)) + timedelta(minutes=rng.randrange(14 * 60))
        return min(local - offset, utc - timedelta(minutes=5))

    def before(a) -> datetime:
        """A few hours to three days ahead of the visit a call booked or changed, in clinic hours."""
        local = a.starts_at - timedelta(minutes=rng.randrange(120, 3 * 24 * 60))
        if not 8 <= local.hour < 22:
            local = local.replace(hour=rng.randrange(8, 22))
        started = local - offset
        return started if oldest < started < utc - timedelta(minutes=5) and local < a.starts_at else any_time()

    plans = []  # (started, kind, appointment or None)
    for _ in range(CALLS):
        roll = rng.random()
        if roll < 0.50 and booked:
            a = booked.pop()
            plans.append((before(a), "booked", a))
        elif roll < 0.80:
            plans.append((any_time(), "info_only", None))
        elif roll < 0.85 and cancelled:
            a = cancelled.pop()
            plans.append((before(a), "cancelled", a))
        elif roll < 0.89 and booked:
            a = booked.pop()
            plans.append((before(a), "moved", a))
        elif roll < 0.96:
            plans.append((any_time(), "no_action", None))
        else:
            plans.append((any_time(), "failed" if roll < 0.985 else "dropped", None))

    # Oldest first, as real calls arrive: the lists page by call id, newest first.
    for started, kind, appt in sorted(plans, key=lambda plan: plan[0]):
        if kind in ("failed", "dropped") and utc - started < timedelta(hours=QUIET_HOURS):
            kind = "info_only"
        if kind == "dropped":  # the worker never finished it
            repo.start_call(s, clinic_id, "call-busy", STACK, "hi", started)
            continue
        items, events, changes, errors = _story(rng, kind, appt)
        c = repo.start_call(s, clinic_id, "call-busy", STACK, "hi", started)
        repo.finish_call(
            s, c.id, ended_at=started + timedelta(seconds=items[-1]["t_ms"] // 1000 + rng.randrange(3, 40)),
            end_reason="error" if kind == "failed" else rng.choice(["agent_ended", "agent_ended", "caller_left"]),
            outcome=kind, turn_count=sum(i["role"] == "caller" for i in items), error_count=errors,
            appointments=changes, events=events, transcript=items, purge_after=transcript_expiry(started),
        )


def _story(rng: random.Random, kind: str, a) -> tuple[list[dict], list[dict], list[dict], int]:
    """(transcript, trace, what it changed, vendor errors) for one call."""
    say = lambda t, role, text: {"t_ms": t, "role": role, "text": text}  # noqa: E731
    items, events, changes, errors = [say(0, "agent", GREETING)], [_ev(60, "clip", None, "greeting")], [], 0
    if kind == "no_action":
        return items, events, changes, errors
    if kind == "booked":
        doctor = a.doctor.name_hi.rsplit(" ", 1)[0]
        items += [
            say(6000, "caller", f"{doctor} का अपॉइंटमेंट चाहिए।"),
            say(9000, "agent", "जी, एक सेकंड, मैं चेक करती हूँ। मरीज़ का नाम और मोबाइल नंबर बता दीजिए।"),
            say(17000, "caller", f"{a.patient.name}, {a.patient.phone}"),
            say(24000, "agent", f"{doctor}, {a.starts_at:%d %B}, {a.patient.name}. क्या यह सही है?"),
            say(29000, "caller", "हाँ, सही है।"),
            say(33000, "agent", "आपका अपॉइंटमेंट बुक हो गया है। धन्यवाद, नमस्ते!"),
        ]
        events += _turn(rng, 6000) + [_ev(9500, "tool", rng.randrange(20, 60), "find_available_slots")]
        events += _turn(rng, 17000) + [_ev(18000, "tool", rng.randrange(20, 60), "check_booking")]
        events += _turn(rng, 29000) + [_ev(30000, "tool", rng.randrange(20, 60), "book_appointment")]
        changes = [{"id": a.id, "action": "booked"}]
    elif kind in ("cancelled", "moved"):
        verb = "कैंसिल करना" if kind == "cancelled" else "आगे बढ़ाना"
        items += [
            say(5000, "caller", f"मुझे अपना अपॉइंटमेंट {verb} है।"),
            say(8000, "agent", "जी, अपना मोबाइल नंबर और मरीज़ का नाम बता दीजिए।"),
            say(15000, "caller", "नंबर वही है जिससे बुक किया था।"),
            say(22000, "agent", "जी, हो गया। और कुछ मदद चाहिए?"),
            say(25000, "caller", "नहीं, बस इतना ही।"),
        ]
        events += _turn(rng, 5000) + _turn(rng, 15000) + [
            _ev(16000, "tool", rng.randrange(20, 60), "find_my_appointments"),
            _ev(20000, "tool", rng.randrange(20, 60), "cancel_appointment" if kind == "cancelled" else "reschedule_appointment"),
        ]
        changes = [{"id": a.id, "action": kind}]
    else:  # a question, or a call that failed part-way
        q, answer = rng.choice([
            ("क्लिनिक कब तक खुला है?", "जी, शाम नौ बजे तक खुला है।"),
            ("पार्किंग है क्या?", "जी, सामने दो-पहिया की पार्किंग है।"),
            ("डॉक्टर की फ़ीस कितनी है?", "जी, पाँच सौ रुपये है।"),
            ("क्या कार्ड से पेमेंट हो जाएगा?", "जी, कैश, यूपीआई और कार्ड सब चलते हैं।"),
        ])
        items.append(say(5000, "caller", q))
        events += _turn(rng, 5000)
        if kind == "failed":
            events.append(_ev(6500, "error", None, "sarvam/bulbul:v3", False, "APIConnectionError, fatal"))
            errors = 1
        else:
            items += [say(8000, "agent", answer), say(12000, "caller", "ठीक है, धन्यवाद।")]
            if rng.random() < 0.05:
                events.append(_ev(8500, "error", None, "sarvam/saaras:v3", False, "APITimeoutError, retried"))
                errors = 1
    return items, events, changes, errors


def _existing(s: Session):
    return next((c for c in repo.list_clinics(s) if c.slug == SLUG), None)


if __name__ == "__main__":
    import sys

    from clinic_agent.config import load_settings
    from clinic_agent.store import migrations
    from clinic_agent.store.db import make_engine, session_factory

    args = sys.argv[1:]
    member = args[args.index("--member") + 1] if "--member" in args else ""
    cfg = load_settings()
    engine = make_engine(cfg.database_url)
    migrations.check(engine)  # never migrates: only the migrations command changes a schema
    with session_factory(engine)() as s:
        old = _existing(s)
        if old and "--replace" not in args:
            raise SystemExit(f"{NAME} is already there (clinic {old.id}). Add --replace to delete it and seed it fresh.")
        if old:
            repo.delete_clinic(s, old.id)
        clinic_id = seed_busy(s, member)
        print(f"seeded {NAME} as clinic {clinic_id} into {cfg.database_url}")
