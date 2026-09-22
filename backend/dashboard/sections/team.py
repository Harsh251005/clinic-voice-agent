"""Who may open this clinic in the dashboard (admins only)."""

import streamlit as st

from clinic_agent.store import repo
from dashboard import data, theme


def render(clinic) -> None:
    with data.session() as s:
        members = repo.list_members(s, clinic.id)

    with theme.card("team"):
        st.markdown('<p class="card-title">People with access</p>', unsafe_allow_html=True)
        st.caption(
            "They sign in with the Google account for that address and see only this clinic. "
            "No invitation email is sent: send them the dashboard's address yourself."
        )
        if not members:
            st.markdown('<p class="muted">Nobody yet. Admins can always open every clinic.</p>', unsafe_allow_html=True)
        for m in members:
            left, right = st.columns([5, 1], vertical_alignment="center")
            left.write(m.email)
            if right.button("Remove", key=f"remove_member_{m.id}"):
                with data.session() as s:
                    repo.remove_member(s, m.id)
                theme.flash(f"{m.email} can no longer open {clinic.name}")
                st.rerun()

    with st.form("add_member", clear_on_submit=True):
        st.markdown('<p class="card-title">Add someone</p>', unsafe_allow_html=True)
        email = st.text_input("Google account email", placeholder="reception@gmail.com")
        if st.form_submit_button("Give access"):
            try:
                with data.session() as s:
                    member = repo.add_member(s, clinic.id, email)
            except ValueError as err:
                st.error(str(err))
                return
            theme.flash(f"{member.email} can now open {clinic.name}")
            st.rerun()
