"""Name, address, phone and booking rules."""

import streamlit as st

from clinic_agent.store import repo
from dashboard import data, theme


def render(clinic) -> None:
    with st.form("clinic_info"):
        st.markdown('<p class="card-title">Clinic details</p>', unsafe_allow_html=True)
        name = st.text_input("Clinic name", clinic.name)
        address = st.text_area("Address", clinic.address)
        phone = st.text_input("Phone", clinic.phone)

        st.markdown('<p class="card-title">Booking rules</p>', unsafe_allow_html=True)
        left, right = st.columns(2)
        window = left.number_input(
            "Book up to (days ahead)", min_value=1, max_value=365, value=clinic.booking_window_days
        )
        offered = right.number_input(
            "Slots offered per question", min_value=1, max_value=6, value=clinic.slots_offered,
            help="How many free times the receptionist reads out at once.",
        )
        if st.form_submit_button("Save details"):
            if not name.strip():
                st.error("The clinic needs a name.")
                return
            with data.session() as s:
                repo.update_clinic(
                    s, clinic.id, name=name.strip(), address=address.strip(), phone=phone.strip(),
                    booking_window_days=int(window), slots_offered=int(offered),
                )
            theme.flash("Clinic details saved")
            st.rerun()
