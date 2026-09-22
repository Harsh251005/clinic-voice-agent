"""Clinic setup: everything the receptionist agent knows comes from here."""

import streamlit as st

from clinic_agent.store import repo
from dashboard import auth, data, theme
from dashboard.sections import call_link, clinic_info, doctors, faq, hours, new_clinic, team, time_off

theme.show_flash()

viewer = auth.viewer()
clinic_id = data.current_clinic_id()
if clinic_id is None or st.session_state.get("_new_clinic"):
    if viewer.is_admin:  # only admins create clinics; members always have one
        new_clinic.render(cancellable=clinic_id is not None)
    st.stop()

with data.session() as s:
    clinic = repo.get_clinic(s, clinic_id)

theme.header(
    clinic.name,
    "Everything the receptionist says about this clinic comes from these details.",
)

names = ["Clinic", "Call link", "Doctors", "Weekly hours", "Time off", "FAQ"]
tabs = st.tabs(names + (["Team"] if viewer.is_admin else []))
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
if viewer.is_admin:
    with tabs[6]:
        team.render(clinic)
