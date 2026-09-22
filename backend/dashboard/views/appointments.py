"""Appointments by day: what the receptionist booked, and staff cancellation."""

from datetime import date, timedelta

import streamlit as st

from clinic_agent.store import repo
from dashboard import data, theme
from dashboard.sections import appointment_list

theme.show_flash()

clinic_id = data.current_clinic_id()
if clinic_id is None:
    theme.header("Appointments", "Set up a clinic first.")
    st.stop()

theme.header("Appointments", "Bookings made on calls appear here as soon as they are confirmed.")

pick, spacer, toggle = st.columns([2, 3, 2], vertical_alignment="bottom")
day = pick.date_input("Day", date.today(), format="DD/MM/YYYY", key="appt_day")
show_cancelled = toggle.toggle("Show cancelled", key="appt_cancelled")

with data.session() as s:
    rows = repo.appointments_on(s, clinic_id, day, include_cancelled=show_cancelled)
    week = [
        len(repo.appointments_on(s, clinic_id, day + timedelta(days=i)))
        for i in range(7)
    ]

booked = [a for a in rows if a.status == "booked"]
a, b, c = st.columns(3)
a.metric("Booked this day", len(booked))
b.metric("Booked on calls", sum(1 for x in booked if x.source == "voice"))
c.metric("Next 7 days", sum(week))

appointment_list.render(rows, day)
