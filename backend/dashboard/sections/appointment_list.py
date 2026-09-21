"""One day's appointments grouped by doctor, with two-step cancellation."""

from datetime import date
from itertools import groupby

import streamlit as st

from clinic_agent.store import repo
from dashboard import data, theme

PAGE = 25  # rows per page: a widget per row gets slow past a few dozen


def render(rows, day: date) -> None:
    if not rows:
        with theme.card("no_appts"):
            st.markdown(
                f'<p class="muted">No appointments on {day:%A, %d %B}.</p>', unsafe_allow_html=True
            )
        return

    pages = max(1, -(-len(rows) // PAGE))
    page = st.session_state.get("appt_page", 1) if pages > 1 else 1
    page = min(page, pages)
    shown = sorted(rows, key=lambda a: (a.doctor.name, a.starts_at))[(page - 1) * PAGE : page * PAGE]

    for doctor, appts in groupby(shown, key=lambda a: a.doctor.name):
        with theme.card(f"appts_{doctor}"):
            st.markdown(f'<p class="card-title">{doctor}</p>', unsafe_allow_html=True)
            for appt in appts:
                _row(appt)

    if pages > 1:
        st.number_input("Page", 1, pages, page, key="appt_page")


def _row(appt) -> None:
    when, who, tags, action = st.columns([1.2, 3, 2.2, 1.6], vertical_alignment="center")
    when.markdown(f"**{appt.starts_at:%I:%M %p}**")
    who.markdown(
        f"{appt.patient.name}  \n<span class='muted'>{_phone(appt.patient.phone)}</span>",
        unsafe_allow_html=True,
    )
    source = theme.pill("Call") if appt.source == "voice" else theme.pill("Staff", "off")
    status = theme.pill("Cancelled", "warn") if appt.status == "cancelled" else ""
    tags.markdown(source + status, unsafe_allow_html=True)

    if appt.status != "booked":
        return
    pending = st.session_state.get("cancel_pending") == appt.id
    if not pending:
        if action.button("Cancel", key=f"cancel_{appt.id}"):
            st.session_state["cancel_pending"] = appt.id
            st.rerun()
        return
    if action.button("Yes, cancel", key=f"confirm_{appt.id}", type="primary"):
        with data.session() as s:
            repo.cancel_appointment(s, appt.id)
        st.session_state.pop("cancel_pending", None)
        theme.flash(f"Cancelled {appt.patient.name}'s {appt.starts_at:%I:%M %p} appointment")
        st.rerun()


def _phone(p: str) -> str:
    return f"{p[:5]} {p[5:]}" if len(p) == 10 else p
