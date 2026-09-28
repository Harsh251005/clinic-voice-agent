"""A lived-in day for the fictional demo clinic: bookings today and this
week, visit marks, leave, a holiday, and two calls with transcripts, all
relative to the clinic's clock now. For demos, screenshots and
`docker compose up`. Fictional people only; never run it on real data.

    uv run python -m seeds.demo_day    # after seeds.demo_clinic, same DATABASE_URL
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from clinic_agent.context import clinic_now
from clinic_agent.store import repo
from clinic_agent.store.db import Session
from clinic_agent.store.models import utc_now
from clinic_agent.store.purge import transcript_expiry

TODAY_ASHA = [  # (hour, minute, name, phone, by the receptionist?, reason, visit)
    (10, 0, "Riya Sharma", "9820012345", True, "Follow-up for fever", "done"),
    (10, 15, "Arjun Mehta", "9820011111", True, "Fever for 3 days", "done"),
    (10, 45, "Sunita Patil", "9820022222", False, "BP check", "no_show"),
    (11, 30, "Farhan Shaikh", "9820033333", True, "Cough and cold", "done"),
    (12, 0, "Priya Nair", "9820044444", True, "Follow-up", "arrived"),
    (17, 0, "Kavita Rao", "9820055555", True, "Stomach pain", None),
    (17, 30, "Deepak Joshi", "9820066666", False, "Diabetes review", None),
    (18, 15, "Ananya Iyer", "9820077777", True, "Skin rash", None),
]
TODAY_ROHAN = [
    (11, 0, "Aarav Kulkarni", "9820088888", True, "Vaccination", "done"),
    (11, 40, "Ishaan Desai", "9820099999", True, "Ear pain", None),
    (13, 0, "Myra Kapoor", "9819011111", False, "Fever", None),
]
LATER = [  # (days ahead, hour, minute, name, phone)
    (1, 10, 0, "Rahul Verma", "9819100001"), (1, 10, 30, "Neha Gupta", "9819100002"),
    (2, 17, 15, "Suresh Menon", "9819100003"), (2, 11, 0, "Pooja Shah", "9819100004"),
    (3, 18, 0, "Vikram Singh", "9819100005"),
]


def seed_day(s: Session, clinic_id: int) -> None:
    clinic = repo.get_clinic(s, clinic_id)
    asha, rohan = clinic.doctors[0], clinic.doctors[1]
    now = clinic_now(clinic.timezone)
    today = now.date()
    # Rohan sits Mon/Wed/Fri: on his other days his patients go to Asha.
    for doctor, rows in ((asha, TODAY_ASHA), (rohan if today.weekday() in (0, 2, 4) else asha, TODAY_ROHAN)):
        for h, m, name, phone, voice, reason, visit in rows:
            try:
                a = repo.book(s, clinic_id, doctor.id, datetime.combine(today, time(h, m)), name, phone,
                              source="voice" if voice else "dashboard", reason=reason)
            except repo.SlotTaken:
                continue
            # Marks only for times already past: the diary looks like the day so far.
            if visit and a.starts_at <= now:
                repo.set_visit(s, a.id, visit)
    for days, h, m, name, phone in LATER:
        day = today + timedelta(days=days)
        if day.weekday() == 6:  # the demo clinic is closed on Sundays
            day += timedelta(days=1)
        try:
            repo.book(s, clinic_id, asha.id, datetime.combine(day, time(h, m)), name, phone, reason="Check-up")
        except repo.SlotTaken:
            pass
    repo.add_time_off(s, clinic_id, today + timedelta(days=3), today + timedelta(days=3),
                      doctor_id=rohan.id, reason="Conference")
    repo.add_time_off(s, clinic_id, today + timedelta(days=5), today + timedelta(days=5), reason="Clinic holiday")
    _calls(s, clinic_id, asha.name)


def _calls(s: Session, clinic_id: int, doctor: str) -> None:
    """Two finished calls: one booking, one question. Their words are the
    transcript (patient data on a real clinic; fictional here)."""
    stack = "sarvam/saaras:v3 · sarvam/sarvam-105b-conversations · sarvam/bulbul:v3"
    utc = utc_now()

    def ev(t, kind, ms, name="", ok=True, detail=""):
        return {"t_ms": t, "kind": kind, "name": name, "duration_ms": ms, "ok": ok, "detail": detail}

    booked = repo.appointments_on(s, clinic_id, clinic_now(repo.get_clinic(s, clinic_id).timezone).date())
    kavita = next((a for a in booked if a.patient.name == "Kavita Rao"), None)
    for ago, outcome, events, items, changes in [
        (timedelta(hours=3), "booked", [
            ev(900, "stt", 310), ev(900, "eou", 540), ev(1400, "llm", 720), ev(1500, "tts", 230),
            ev(1500, "reply", 1480), ev(9000, "tool", 41, "check_booking"), ev(15000, "tool", 36, "book_appointment"),
        ], [
            {"t_ms": 0, "role": "agent", "text": "नमस्ते, Demo Family Clinic से बात कर रही हूँ, मैं क्लिनिक की ऑटोमेटेड असिस्टेंट हूँ। बताइए, मैं आपकी क्या मदद कर सकती हूँ?"},
            {"t_ms": 4200, "role": "caller", "text": "आज शाम को डॉक्टर आशा का अपॉइंटमेंट मिलेगा? पेट में दर्द है।"},
            {"t_ms": 6100, "role": "agent", "text": "जी, आज शाम पाँच बजे का समय खाली है। मरीज़ का नाम और मोबाइल नंबर बताइए।"},
            {"t_ms": 11800, "role": "caller", "text": "कविता राव, नंबर 98200 55555"},
            {"t_ms": 13900, "role": "agent", "text": f"{doctor}, आज शाम पाँच बजे, कविता राव, नंबर 9 8 2 0 0 5 5 5 5 5. क्या यह सही है?"},
            {"t_ms": 17200, "role": "caller", "text": "हाँ, सही है।"},
            {"t_ms": 18600, "role": "agent", "text": "आपका अपॉइंटमेंट बुक हो गया है। आज शाम पाँच बजे मिलते हैं। धन्यवाद!"},
        ], [{"id": kavita.id, "action": "booked"}] if kavita else []),
        (timedelta(minutes=40), "info_only", [ev(800, "llm", 650), ev(900, "tts", 210), ev(900, "reply", 1320)], [
            {"t_ms": 0, "role": "agent", "text": "नमस्ते, Demo Family Clinic से बात कर रही हूँ, मैं क्लिनिक की ऑटोमेटेड असिस्टेंट हूँ। बताइए, मैं आपकी क्या मदद कर सकती हूँ?"},
            {"t_ms": 3500, "role": "caller", "text": "Parking hai kya clinic pe?"},
            {"t_ms": 5000, "role": "agent", "text": "जी, सामने दो-पहिया वाहनों की पार्किंग है। और कुछ?"},
            {"t_ms": 8200, "role": "caller", "text": "Nahi, bas itna hi. Thank you."},
            {"t_ms": 9400, "role": "agent", "text": "धन्यवाद, आपका दिन शुभ हो!"},
        ], []),
    ]:
        started = utc - ago
        c = repo.start_call(s, clinic_id, "call-demo", stack, started)
        repo.finish_call(
            s, c.id, ended_at=started + timedelta(seconds=items[-1]["t_ms"] // 1000 + 3), end_reason="agent_ended",
            outcome=outcome, turn_count=sum(i["role"] == "caller" for i in items), error_count=0,
            appointments=changes, events=events, transcript=items, purge_after=transcript_expiry(started),
        )


if __name__ == "__main__":
    from clinic_agent.config import load_settings
    from clinic_agent.store.db import sessions_for

    with sessions_for(load_settings().database_url)() as s:
        clinics = repo.list_clinics(s)
        if [c.name for c in clinics] != ["Demo Family Clinic"]:
            raise SystemExit("seeds.demo_day fills only a database holding just the demo clinic; not touching this one")
        if repo.has_calls(s, clinics[0].id):
            raise SystemExit(0)  # already filled: running it again changes nothing
        seed_day(s, clinics[0].id)
        print(f"filled a demo day for clinic {clinics[0].id}")
