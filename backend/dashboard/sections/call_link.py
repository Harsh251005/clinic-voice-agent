"""The clinic's call link: what patients open to talk to the receptionist."""

import streamlit as st

from clinic_agent.config import load_settings
from clinic_agent.store import repo
from dashboard import data, theme


def render(clinic) -> None:
    link = f"{load_settings().public_base_url}/call/{clinic.slug}"
    with theme.card("call_link"):
        st.markdown('<p class="card-title">Share this link</p>', unsafe_allow_html=True)
        st.caption(
            "Patients open it on their phone or computer and talk to the receptionist "
            "in the browser. Put it on your website, WhatsApp or Google listing."
        )
        st.code(link, language=None)

    with st.form("call_link_name"):
        st.markdown('<p class="card-title">Link name</p>', unsafe_allow_html=True)
        slug = st.text_input(
            "Link name", clinic.slug,
            help="Lowercase letters, digits and hyphens, e.g. sharma-skin.",
        )
        st.caption("Changing it stops the old link from working: update it everywhere you shared it.")
        if st.form_submit_button("Save link name"):
            try:
                with data.session() as s:
                    repo.set_slug(s, clinic.id, slug.strip().lower())
            except ValueError as err:
                st.error(str(err))
                return
            theme.flash("Link name saved")
            st.rerun()
