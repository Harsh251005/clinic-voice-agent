"""Database access for the dashboard: one engine per server, a session per rerun.

Everything goes through `clinic_agent.store.repo`, the same functions the
agent uses, so the dashboard never has its own idea of the schema.
"""

from __future__ import annotations

from contextlib import contextmanager

import streamlit as st

from clinic_agent.config import load_settings
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for


@st.cache_resource
def _sessions():
    return sessions_for(load_settings().database_url)


@contextmanager
def session():
    with _sessions()() as s:
        yield s


def clinics_for(viewer) -> list:
    """The clinics this viewer may open: every clinic for an admin."""
    with session() as s:
        return [c for c in repo.list_clinics(s) if viewer.may_open(c.id)]


def current_clinic_id() -> int | None:
    """The clinic picked in the sidebar, or None if there are no clinics yet.
    Checked against the viewer on every read, not only when the list is drawn."""
    from dashboard import auth

    clinic_id = st.session_state.get("clinic_id")
    if clinic_id is None or not auth.viewer().may_open(clinic_id):
        return None
    return clinic_id
