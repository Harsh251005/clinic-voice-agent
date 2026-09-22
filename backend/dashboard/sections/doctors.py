"""Doctors: add, edit, and switch on/off.

There is deliberately no delete: removing a doctor would also remove their
appointment history. Inactive doctors are never offered to callers.
"""

import streamlit as st

from clinic_agent.store import repo
from dashboard import data, schedules, theme


def render(clinic) -> None:
    if not clinic.doctors:
        st.markdown('<p class="muted">No doctors yet. Add the first one below.</p>', unsafe_allow_html=True)

    for doc in clinic.doctors:
        with theme.card(f"doctor_{doc.id}"):
            info, action = st.columns([5, 1])
            status = theme.pill("Active") if doc.active else theme.pill("Inactive", "off")
            info.markdown(f'<p class="card-title">{doc.name}</p>', unsafe_allow_html=True)
            info.markdown(
                status
                + theme.pill(doc.specialty or "No specialty", "off")
                + theme.pill(f"₹{doc.fee}", "off")
                + theme.pill(f"{doc.slot_minutes} min slots", "off"),
                unsafe_allow_html=True,
            )
            if action.button("Deactivate" if doc.active else "Activate", key=f"toggle_{doc.id}"):
                with data.session() as s:
                    repo.update_doctor(s, doc.id, active=not doc.active)
                theme.flash(f"{doc.name} {'deactivated' if doc.active else 'activated'}")
                st.rerun()
            with st.expander("Edit"):
                _doctor_form(f"edit_{doc.id}", doc)

    _doctor_form("add_doctor", None, clinic.id, title="Add a doctor", colleagues=clinic.doctors)


def _doctor_form(key: str, doc, clinic_id: int | None = None, title: str = "", colleagues=()) -> None:
    with st.form(key, clear_on_submit=doc is None, border=doc is None):
        if title:
            st.markdown(f'<p class="card-title">{title}</p>', unsafe_allow_html=True)
        name = st.text_input("Name", doc.name if doc else "", placeholder="Dr. Asha Mehta")
        specialty = st.text_input("Specialty", doc.specialty if doc else "", placeholder="General Physician")
        left, right = st.columns(2)
        fee = left.number_input("Consultation fee (₹)", min_value=0, step=50, value=doc.fee if doc else 500)
        slot = right.number_input(
            "Slot length (minutes)", min_value=5, max_value=120, step=5, value=doc.slot_minutes if doc else 15
        )
        starting = {}
        if doc is None:
            # A new doctor starts with a full week to adjust, not an empty one.
            starting = dict(schedules.PRESETS)
            starting.update({f"Same as {d.name}": schedules.same_as(d) for d in colleagues if d.hours})
            starting[schedules.NONE] = []
            start_with = st.selectbox(
                "Starting hours", list(starting), index=0,
                help="Adjust them afterwards on the Weekly hours tab.",
            )
        if st.form_submit_button("Save doctor" if doc else "Add doctor"):
            if not name.strip():
                st.error("The doctor needs a name.")
                return
            fields = dict(name=name.strip(), specialty=specialty.strip(), fee=int(fee), slot_minutes=int(slot))
            with data.session() as s:
                if doc:
                    repo.update_doctor(s, doc.id, **fields)
                else:
                    new = repo.add_doctor(s, clinic_id, **fields)
                    repo.set_doctor_hours(s, new.id, starting[start_with])
            if doc or not starting[start_with]:
                theme.flash(f"{fields['name']} saved")
            else:
                # Assumed hours become bookable at once, so say so.
                theme.flash(f"{fields['name']} added with {start_with}. Check them on the Weekly hours tab.")
            st.rerun()
