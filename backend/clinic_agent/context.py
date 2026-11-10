"""What a call needs to know about its clinic, loaded once when the call starts."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from clinic_agent.call_settings import CallSettings, merge
from clinic_agent.config import Settings
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for
from clinic_agent.store.models import Clinic, TimeOff


def clinic_now(timezone: str) -> datetime:
    """Current wall-clock time at the clinic, naive, matching stored times."""
    return datetime.now(ZoneInfo(timezone)).replace(tzinfo=None)


def load_clinic(cfg: Settings, clinic_id: int) -> tuple[Clinic, list[TimeOff], CallSettings]:
    """The clinic, its leave/holidays inside the booking window, and the
    call's settings (the dashboard's, over .env: call_settings.py).

    Blocking (database I/O): call it with asyncio.to_thread from a call.
    Raises repo.NotFound if the clinic is not in the database.
    """
    with sessions_for(cfg.database_url)() as s:
        clinic = repo.get_clinic(s, clinic_id)
        today = clinic_now(clinic.timezone).date()
        time_off = repo.time_off_overlapping(
            s, clinic.id, today, today + timedelta(days=clinic.booking_window_days)
        )
        settings = merge(cfg, repo.system_settings(s), clinic)
    return clinic, time_off, settings


def every_clinics_settings(cfg: Settings) -> list[tuple[str, CallSettings]]:
    """(clinic name, its call settings) for every active clinic, or one
    ("", shared settings) when there is none: the worker's start-up check
    tries each clinic's own voice, since a clinic's speaker must suit the
    shared voice model."""
    with sessions_for(cfg.database_url)() as s:
        system = repo.system_settings(s)
        clinics = [c for c in repo.list_clinics(s) if c.active]
        return [(c.name, merge(cfg, system, c)) for c in clinics] or [("", merge(cfg, system, None))]


def local_clinic(cfg: Settings, requested: int | None) -> int:
    """The clinic a local test call (console, or dev without a dispatch) is for:
    the one asked for, or the only clinic there is. Never used in production.

    Raises repo.NotFound with a message that says what to do.
    """
    with sessions_for(cfg.database_url)() as s:
        if requested is not None:
            return repo.get_clinic(s, requested).id
        clinics = repo.list_clinics(s)
    if len(clinics) == 1:
        return clinics[0].id
    if not clinics:
        raise repo.NotFound(
            f"no clinics in {cfg.database_url}. Create one in the dashboard "
            "or run: uv run python -m seeds.demo_clinic"
        )
    listed = ", ".join(f"{c.id} = {c.name}" for c in clinics)
    raise repo.NotFound(f"several clinics, pick one with --clinic <id> ({listed})")
