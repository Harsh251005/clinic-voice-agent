"""Weekly sittings per doctor, edited as one table. Two rows on a day = split shift."""

from datetime import time

import pandas as pd
import streamlit as st

from clinic_agent.store import repo
from dashboard import data, theme

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def render(clinic) -> None:
    if not clinic.doctors:
        st.markdown('<p class="muted">Add a doctor first.</p>', unsafe_allow_html=True)
        return

    names = {d.id: d.name for d in clinic.doctors}
    doctor_id = st.selectbox("Doctor", list(names), format_func=names.get, key="hours_doctor")
    doctor = next(d for d in clinic.doctors if d.id == doctor_id)

    with theme.card("hours"):
        st.markdown('<p class="card-title">Weekly sittings</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="muted">One row per sitting. Add two rows for the same day for a morning '
            "and an evening sitting. Days with no rows are days off.</p>",
            unsafe_allow_html=True,
        )
        table = pd.DataFrame(
            [{"Day": DAYS[h.weekday], "Start": h.start, "End": h.end} for h in doctor.hours],
            columns=["Day", "Start", "End"],
        )
        edited = st.data_editor(
            table,
            key=f"hours_{doctor_id}",
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "Day": st.column_config.SelectboxColumn(options=DAYS, required=True),
                "Start": st.column_config.TimeColumn(format="h:mm a", step=300, required=True),
                "End": st.column_config.TimeColumn(format="h:mm a", step=300, required=True),
            },
        )
        if st.button("Save hours", type="primary", key=f"save_hours_{doctor_id}"):
            rows = edited.dropna(how="all")
            if rows.isna().any(axis=None):
                st.error("Every row needs a day, a start and an end.")
                return
            sittings = [(DAYS.index(r.Day), _as_time(r.Start), _as_time(r.End)) for r in rows.itertuples()]
            try:
                with data.session() as s:
                    repo.set_doctor_hours(s, doctor_id, sittings)
            except ValueError as err:
                st.error(str(err))
                return
            theme.flash(f"Hours saved for {doctor.name}")
            st.rerun()


def _as_time(value) -> time:
    return value if isinstance(value, time) else pd.Timestamp(str(value)).time()
