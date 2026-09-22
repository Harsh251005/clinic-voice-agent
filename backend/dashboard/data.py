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


def clinics() -> list:
    with session() as s:
        return repo.list_clinics(s)


def current_clinic_id() -> int | None:
    """The clinic picked in the sidebar, or None if there are no clinics yet."""
    return st.session_state.get("clinic_id")
