"""What a call needs to know about its clinic, loaded once when the call starts."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from clinic_agent.config import Settings
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for
from clinic_agent.store.models import Clinic, TimeOff


def clinic_now(timezone: str) -> datetime:
    """Current wall-clock time at the clinic, naive, matching stored times."""
    return datetime.now(ZoneInfo(timezone)).replace(tzinfo=None)


def load_clinic(cfg: Settings) -> tuple[Clinic, list[TimeOff]]:
    """The clinic and its leave/holidays inside the booking window.

    Blocking (database I/O): call it with asyncio.to_thread from a call.
    Raises repo.NotFound if CLINIC_ID is not in the database.
    """
    with sessions_for(cfg.database_url)() as s:
        clinic = repo.get_clinic(s, cfg.clinic_id)
        today = clinic_now(clinic.timezone).date()
        time_off = repo.time_off_overlapping(
            s, clinic.id, today, today + timedelta(days=clinic.booking_window_days)
        )
    return clinic, time_off
