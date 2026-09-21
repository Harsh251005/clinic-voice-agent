"""Doctor leave and whole-clinic holidays. Callers are never offered these days."""

from datetime import date

import streamlit as st

from clinic_agent.store import repo
from dashboard import data, theme

WHOLE_CLINIC = 0


def render(clinic) -> None:
    names = {d.id: d.name for d in clinic.doctors}
    today = date.today()
    with data.session() as s:
        upcoming = repo.time_off_overlapping(s, clinic.id, today, date(today.year + 5, 12, 31))

    with theme.card("time_off"):
        st.markdown('<p class="card-title">Upcoming</p>', unsafe_allow_html=True)
        if not upcoming:
            st.markdown('<p class="muted">No leave or holidays planned.</p>', unsafe_allow_html=True)
        for off in upcoming:
            who, when, action = st.columns([2, 3, 1])
            who.markdown(
                theme.pill(names.get(off.doctor_id, "Whole clinic"), "warn" if off.doctor_id is None else ""),
                unsafe_allow_html=True,
            )
            span = off.date_from.strftime("%d %b %Y")
            if off.date_to != off.date_from:
                span += " → " + off.date_to.strftime("%d %b %Y")
            when.markdown(f"{span}  <span class='muted'>{off.reason}</span>", unsafe_allow_html=True)
            if action.button("Remove", key=f"off_{off.id}"):
                with data.session() as s:
                    repo.delete_time_off(s, off.id)
                theme.flash("Removed")
                st.rerun()

    with st.form("add_time_off", clear_on_submit=True):
        st.markdown('<p class="card-title">Add leave or a holiday</p>', unsafe_allow_html=True)
        choices = {WHOLE_CLINIC: "Whole clinic (holiday)", **names}
        who = st.selectbox("Who", list(choices), format_func=choices.get)
        left, right = st.columns(2)
        start = left.date_input("From", today, format="DD/MM/YYYY")
        end = right.date_input("To", today, format="DD/MM/YYYY")
        reason = st.text_input("Reason (optional)", placeholder="Diwali")
        if st.form_submit_button("Add"):
            try:
                with data.session() as s:
                    repo.add_time_off(
                        s, clinic.id, start, end,
                        doctor_id=None if who == WHOLE_CLINIC else who, reason=reason.strip(),
                    )
            except ValueError as err:
                st.error(str(err))
                return
            theme.flash("Added")
            st.rerun()
