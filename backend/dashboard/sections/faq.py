"""Free-form facts the receptionist may repeat: parking, payment, reports..."""

import streamlit as st

from clinic_agent.store import repo
from dashboard import data, theme


def render(clinic) -> None:
    with theme.card("faq"):
        st.markdown('<p class="card-title">What callers often ask</p>', unsafe_allow_html=True)
        if not clinic.faq:
            st.markdown('<p class="muted">Nothing added yet.</p>', unsafe_allow_html=True)
        for item in clinic.faq:
            text, action = st.columns([6, 1])
            text.markdown(f"**{item.question}**  \n{item.answer}")
            if action.button("Remove", key=f"faq_{item.id}"):
                with data.session() as s:
                    repo.delete_faq(s, item.id)
                theme.flash("Removed")
                st.rerun()

    with st.form("add_faq", clear_on_submit=True):
        st.markdown('<p class="card-title">Add an answer</p>', unsafe_allow_html=True)
        question = st.text_input("Question", placeholder="Do you accept UPI?")
        answer = st.text_area("Answer", placeholder="Yes — cash, UPI and cards are all accepted.")
        if st.form_submit_button("Add"):
            if not question.strip() or not answer.strip():
                st.error("Both a question and an answer are needed.")
                return
            with data.session() as s:
                repo.add_faq(s, clinic.id, question.strip(), answer.strip())
            theme.flash("Added")
            st.rerun()
