#!/usr/bin/env bash
# The API for end-to-end tests: a fresh throwaway database (never your real
# data), the demo clinic, one booking today, and sign-in off. Every value the
# API needs is set here, so a developer's .env can't leak in.
set -euo pipefail
cd "$(dirname "$0")/../../backend"
mkdir -p data
rm -f data/e2e.db
export DATABASE_URL="sqlite:///$PWD/data/e2e.db"
export DASHBOARD_LOGIN=off ADMIN_EMAILS= API_HOST=127.0.0.1 API_PORT=8095
export PUBLIC_BASE_URL=http://127.0.0.1:8095 DASHBOARD_URL=http://localhost:3200
export LIVEKIT_URL=wss://e2e.invalid LIVEKIT_API_KEY=e2e LIVEKIT_API_SECRET=e2e-only-secret-not-used-for-real-calls
uv run python -m clinic_agent.store.migrations
uv run python - <<'PY'
from datetime import datetime, time
from clinic_agent.config import load_settings
from clinic_agent.context import clinic_now
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for
from seeds.demo_clinic import seed_demo

with sessions_for(load_settings().database_url)() as s:
    clinic_id = seed_demo(s)
    clinic = repo.get_clinic(s, clinic_id)
    today = clinic_now(clinic.timezone).date()
    appt = repo.book(s, clinic_id, clinic.doctors[0].id, datetime.combine(today, time(10, 0)), "Riya Sharma", "9820012345")

    # Three calls for the admin panel: one booking, one that hit a vendor
    # error, one the worker never finished.
    from datetime import timedelta
    from clinic_agent.store.models import utc_now
    stack = "sarvam/saaras:v3 · openai/gpt-6-luna · sarvam/bulbul:v3"
    now = utc_now()
    def ev(t, kind, ms, name="", ok=True, detail=""):
        return {"t_ms": t, "kind": kind, "name": name, "duration_ms": ms, "ok": ok, "detail": detail}
    def call(ago, outcome, events, items, changes=(), finished=True):
        started = now - ago
        c = repo.start_call(s, clinic_id, "e2e", stack, started)
        if finished:
            repo.finish_call(s, c.id, ended_at=started + timedelta(seconds=84), end_reason="agent_ended", outcome=outcome,
                             turn_count=sum(i["role"] == "caller" for i in items), error_count=sum(e["kind"] == "error" for e in events),
                             appointments=list(changes), events=events, transcript=items, purge_after=started + timedelta(days=30))
    call(timedelta(minutes=50), "booked", [
        ev(900, "stt", 310), ev(900, "eou", 620), ev(1400, "llm", 780), ev(1500, "tts", 240), ev(1500, "reply", 1650),
        ev(9000, "tool", 42, "check_booking"), ev(15000, "tool", 37, "book_appointment"),
    ], [
        {"t_ms": 0, "role": "agent", "text": "नमस्ते, Demo Family Clinic से बात कर रही हूँ।"},
        {"t_ms": 4000, "role": "caller", "text": "कल सुबह डॉक्टर आशा का टाइम है?"},
        {"t_ms": 9000, "role": "tool", "tool": "check_booking", "ok": True, "args": "{}", "text": "Not booked yet."},
        {"t_ms": 12000, "role": "caller", "text": "हाँ, सही है"},
    ], [{"id": appt.id, "action": "booked"}])
    call(timedelta(minutes=20), "info_only", [
        ev(800, "llm", 2900), ev(900, "error", None, "sarvam/bulbul:v3", False, "APIConnectionError, retried"),
    ], [{"t_ms": 0, "role": "caller", "text": "पार्किंग है क्या?"}])
    call(timedelta(hours=3), "", [], [], finished=False)
PY
exec uv run python -m api
