"""Drive the dashboard like a user: fill forms, click, then check the database."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from clinic_agent.store import repo
from clinic_agent.store.db import init_db, make_engine, session_factory
from seeds.demo_clinic import seed_demo

APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")


@pytest.fixture
def db_url(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/dash.db"
    monkeypatch.setenv("DATABASE_URL", url)
    st.cache_resource.clear()  # the engine is cached per server process
    yield url
    st.cache_resource.clear()


def sessions(url):
    engine = make_engine(url)
    init_db(engine)
    return session_factory(engine)


def run(page: str | None = None):
    at = AppTest.from_file(APP, default_timeout=30).run()
    if page:
        at.switch_page(page).run()
    assert not at.exception, at.exception
    return at


def setup_page():
    return run("pages/setup.py")


def test_first_run_creates_a_clinic(db_url):
    at = setup_page()
    assert any("Set up your clinic" in m.value for m in at.markdown)
    at.text_input[0].input("Sharma Family Clinic")
    at.button[0].click().run()
    assert not at.exception
    with sessions(db_url)() as s:
        assert [c.name for c in repo.list_clinics(s)] == ["Sharma Family Clinic"]


@pytest.fixture
def seeded(db_url):
    with sessions(db_url)() as s:
        clinic_id = seed_demo(s)
    return db_url, clinic_id


def test_setup_page_renders_all_sections(seeded):
    at = setup_page()
    assert [t.label for t in at.tabs] == ["Clinic", "Doctors", "Weekly hours", "Time off", "FAQ"]
    text = " ".join(m.value for m in at.markdown)
    assert "Dr. Asha Mehta" in text and "Is there parking?" in text


def test_editing_clinic_details_saves_them(seeded):
    url, clinic_id = seeded
    at = setup_page()
    name_box = next(t for t in at.text_input if t.label == "Clinic name")
    name_box.input("Demo Clinic Renamed")
    next(b for b in at.button if b.label == "Save details").click().run()
    assert not at.exception
    with sessions(url)() as s:
        assert repo.get_clinic(s, clinic_id).name == "Demo Clinic Renamed"


def test_adding_a_doctor(seeded):
    url, clinic_id = seeded
    at = setup_page()
    form_inputs = [t for t in at.text_input if t.label == "Name"]
    form_inputs[-1].input("Dr. Neha Kulkarni")  # the last "Name" box is the add form
    next(b for b in reversed(at.button) if b.label == "Add doctor").click().run()
    assert not at.exception
    with sessions(url)() as s:
        assert "Dr. Neha Kulkarni" in [d.name for d in repo.get_clinic(s, clinic_id).doctors]


def test_deactivating_a_doctor(seeded):
    url, clinic_id = seeded
    at = setup_page()
    next(b for b in at.button if b.label == "Deactivate").click().run()
    assert not at.exception
    with sessions(url)() as s:
        assert repo.get_clinic(s, clinic_id).doctors[0].active is False


# ---------- appointments page ----------

def _book_today(url, clinic_id, hour, name, phone, source="voice"):
    from datetime import date, datetime, time

    with sessions(url)() as s:
        doctor = repo.get_clinic(s, clinic_id).doctors[0]
        return repo.book(
            s, clinic_id, doctor.id, datetime.combine(date.today(), time(hour)), name, phone, source=source
        ).id


def test_appointments_page_is_the_landing_page_and_lists_bookings(seeded):
    url, clinic_id = seeded
    _book_today(url, clinic_id, 10, "Ravi Kumar", "9876543210")
    _book_today(url, clinic_id, 11, "Sunita Rao", "9123456780", source="dashboard")
    at = run()
    text = " ".join(m.value for m in at.markdown)
    assert "Ravi Kumar" in text and "98765 43210" in text and "Sunita Rao" in text
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Booked this day"] == "2" and metrics["Booked on calls"] == "1"


def test_cancel_needs_a_second_click(seeded):
    url, clinic_id = seeded
    appt_id = _book_today(url, clinic_id, 10, "Ravi Kumar", "9876543210")
    at = run()
    at.button(key=f"cancel_{appt_id}").click().run()
    with sessions(url)() as s:  # first click only asks
        assert s.get(repo.Appointment, appt_id).status == "booked"
    at.button(key=f"confirm_{appt_id}").click().run()
    assert not at.exception
    with sessions(url)() as s:
        assert s.get(repo.Appointment, appt_id).status == "cancelled"


def test_empty_day(seeded):
    at = run()
    assert any("No appointments on" in m.value for m in at.markdown)
