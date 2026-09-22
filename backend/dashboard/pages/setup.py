"""Clinic setup: everything the receptionist agent knows comes from here."""

import streamlit as st

from clinic_agent.store import repo
from dashboard import data, theme
from dashboard.sections import call_link, clinic_info, doctors, faq, hours, new_clinic, time_off

theme.show_flash()

clinic_id = data.current_clinic_id()
if clinic_id is None:
    new_clinic.render()
    st.stop()

with data.session() as s:
    clinic = repo.get_clinic(s, clinic_id)

theme.header(
    clinic.name,
    "Everything the receptionist says about this clinic comes from these details.",
)

tabs = st.tabs(["Clinic", "Call link", "Doctors", "Weekly hours", "Time off", "FAQ"])
with tabs[0]:
    clinic_info.render(clinic)
with tabs[1]:
    call_link.render(clinic)
with tabs[2]:
    doctors.render(clinic)
with tabs[3]:
    hours.render(clinic)
with tabs[4]:
    time_off.render(clinic)
with tabs[5]:
    faq.render(clinic)
