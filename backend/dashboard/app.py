"""Clinic dashboard.  Run from backend/:  uv run streamlit run dashboard/app.py"""

import sys
from pathlib import Path

# backend/ isn't an installed package (uv package = false), and Streamlit only
# puts this file's folder on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from clinic_agent.store.migrations import SchemaOutdated  # noqa: E402
from dashboard import data, theme  # noqa: E402

st.set_page_config(page_title="Clinic Console", page_icon="🩺", layout="wide")
theme.apply()

try:
    clinics = data.clinics()
except SchemaOutdated as err:
    # The dashboard never migrates: that is a deploy step (migrations.py).
    st.error(str(err))
    st.stop()

with st.sidebar:
    st.markdown('<p class="brand">Clinic <span>Console</span></p>', unsafe_allow_html=True)
    if clinics:
        ids = [c.id for c in clinics]
        names = {c.id: c.name for c in clinics}
        current = st.session_state.get("clinic_id")
        st.session_state["clinic_id"] = st.selectbox(
            "Clinic",
            ids,
            index=ids.index(current) if current in ids else 0,
            format_func=names.get,
        )
    else:
        st.session_state["clinic_id"] = None

page = st.navigation([
    st.Page("pages/appointments.py", title="Appointments", icon=":material/event:", default=True),
    st.Page("pages/setup.py", title="Clinic setup", icon=":material/tune:"),
])
page.run()
