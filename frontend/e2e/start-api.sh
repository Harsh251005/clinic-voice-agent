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
    repo.book(s, clinic_id, clinic.doctors[0].id, datetime.combine(today, time(10, 0)), "Riya Sharma", "9820012345")
PY
exec uv run python -m api
