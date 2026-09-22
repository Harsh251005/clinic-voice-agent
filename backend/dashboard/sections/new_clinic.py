"""A new clinic: the first run, or an admin adding another one."""

import streamlit as st

from clinic_agent.store import repo
from dashboard import data, theme


def render(cancellable: bool = False) -> None:
    theme.header("Set up your clinic", "Start with the basics — you can add doctors and hours next.")
    with st.form("new_clinic"):
        name = st.text_input("Clinic name", placeholder="Sharma Family Clinic")
        address = st.text_area("Address", placeholder="Shop 4, Sunrise Apartments, Borivali East, Mumbai")
        phone = st.text_input("Phone", placeholder="022 1234 5678")
        if st.form_submit_button("Create clinic"):
            if not name.strip():
                st.error("The clinic needs a name.")
                return
            with data.session() as s:
                clinic = repo.create_clinic(s, name=name.strip(), address=address.strip(), phone=phone.strip())
            st.session_state["clinic_id"] = clinic.id
            st.session_state["_new_clinic"] = False
            theme.flash(f"{clinic.name} created")
            st.rerun()
    if cancellable and st.button("Cancel"):
        st.session_state["_new_clinic"] = False
        st.rerun()
