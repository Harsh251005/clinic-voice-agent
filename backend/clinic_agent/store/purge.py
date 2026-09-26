"""Deleting call records once they are past keeping.

    uv run python -m clinic_agent.store.purge    # delete what has expired, now

Transcripts are patient data and go after TRANSCRIPT_DAYS. A call's trace
holds no content and is kept longer, for spotting slow or failing vendors
over time. The API server also runs this every few hours (api/app.py).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from clinic_agent.store import repo
from clinic_agent.store.db import Sessions
from clinic_agent.store.models import utc_now

logger = logging.getLogger("clinic-agent.purge")

TRANSCRIPT_DAYS = 30  # Harsh, 2026-09-23
TRACE_DAYS = 180


def transcript_expiry(started_at: datetime) -> datetime:
    return started_at + timedelta(days=TRANSCRIPT_DAYS)


def purge(sessions: Sessions, now: datetime | None = None) -> tuple[int, int]:
    """Returns (transcripts, calls) deleted."""
    now = now or utc_now()
    with sessions() as s:
        transcripts, calls = repo.purge_expired(s, now, now - timedelta(days=TRACE_DAYS))
    if transcripts or calls:
        logger.info("purged %d transcripts and %d old calls", transcripts, calls)
    return transcripts, calls


if __name__ == "__main__":
    from clinic_agent.config import load_settings
    from clinic_agent.store.db import sessions_for

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    transcripts, calls = purge(sessions_for(load_settings().database_url))
    print(f"deleted {transcripts} transcripts and {calls} old calls")
