"""Drive the dashboard like a user: fill forms, click, then check the database."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from clinic_agent.store import repo
from clinic_agent.store import migrations
from clinic_agent.store.db import make_engine, session_factory
from seeds.demo_clinic import seed_demo

APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")


@pytest.fixture
def db_url(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/dash.db"
    migrations.upgrade(make_engine(url))  # a deploy step, not the dashboard's job
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DASHBOARD_LOGIN", "off")  # admin view; sign-in has its own tests below
    st.cache_resource.clear()  # the engine is cached per server process
    yield url
    st.cache_resource.clear()


def sessions(url):
    engine = make_engine(url)
    migrations.upgrade(engine)
    return session_factory(engine)


def run(page: str | None = None):
    at = AppTest.from_file(APP, default_timeout=30).run()
    if page:
        at.switch_page(page).run()
    assert not at.exception, at.exception
    return at


def setup_page():
    return run("views/setup.py")


def test_unmigrated_database_shows_what_to_run(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/none.db")
    monkeypatch.setenv("DASHBOARD_LOGIN", "off")
    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=30).run()
    st.cache_resource.clear()
    assert not at.exception
    assert any("python -m clinic_agent.store.migrations" in e.value for e in at.error)


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
    assert [t.label for t in at.tabs] == ["Clinic", "Call link", "Doctors", "Weekly hours", "Time off", "FAQ", "Team"]
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


def test_call_link_is_shown_and_its_name_can_change(seeded, monkeypatch):
    db_url, clinic_id = seeded
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://calls.example.in/")
    at = setup_page()
    assert any(c.value == "https://calls.example.in/call/demo-family-clinic" for c in at.code)

    next(t for t in at.text_input if t.label == "Link name").input("demo-clinic")
    next(b for b in at.button if b.label == "Save link name").click().run()
    assert not at.exception
    with sessions(db_url)() as s:
        assert repo.get_clinic(s, clinic_id).slug == "demo-clinic"


def test_invalid_link_name_is_explained_not_saved(seeded):
    db_url, clinic_id = seeded
    at = setup_page()
    next(t for t in at.text_input if t.label == "Link name").input("Demo Clinic!")
    next(b for b in at.button if b.label == "Save link name").click().run()
    assert any("lowercase letters" in e.value for e in at.error)
    with sessions(db_url)() as s:
        assert repo.get_clinic(s, clinic_id).slug == "demo-family-clinic"


# ---------- sign-in and access ----------

@pytest.fixture
def two_clinics(db_url, monkeypatch):
    """Demo clinic (1) and Cure Dental (2); reception@cure.in may open only 2."""
    with sessions(db_url)() as s:
        demo = seed_demo(s)
        cure = repo.create_clinic(s, name="Cure Dental Clinic").id
        repo.add_member(s, cure, "reception@cure.in")
    monkeypatch.setenv("DASHBOARD_LOGIN", "google")
    monkeypatch.setenv("ADMIN_EMAILS", "harsh@example.com")
    monkeypatch.setattr("dashboard.auth.login_configured", lambda: True)
    return demo, cure


def signed_in(monkeypatch, email):
    monkeypatch.setattr("dashboard.auth.google_email", lambda: email)


def _text(at):
    return " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)


def test_login_not_configured_explains_setup(db_url, monkeypatch):
    monkeypatch.setenv("DASHBOARD_LOGIN", "google")
    monkeypatch.setattr("dashboard.auth.login_configured", lambda: False)  # ignore a real secrets.toml
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert "Sign-in isn't set up" in _text(at)
    assert not at.sidebar.selectbox  # nothing of any clinic is drawn


def test_signed_out_sees_only_sign_in(two_clinics, monkeypatch):
    signed_in(monkeypatch, None)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert [b.label for b in at.button] == ["Sign in with Google"]
    assert "Cure Dental" not in _text(at) and "Demo Family" not in _text(at)


def test_member_sees_only_their_clinic(two_clinics, monkeypatch):
    demo, cure = two_clinics
    signed_in(monkeypatch, "reception@cure.in")
    at = run()  # AppTest's switch_page runs only the page, so read the sidebar first
    assert at.sidebar.selectbox[0].options == ["Cure Dental Clinic"]
    assert "New clinic" not in [b.label for b in at.sidebar.button]
    assert any("Signed in as reception@cure.in" in c.value for c in at.sidebar.caption)
    at.switch_page("views/setup.py").run()
    assert "Team" not in [t.label for t in at.tabs]


def test_stranger_is_told_to_ask_for_access(two_clinics, monkeypatch):
    signed_in(monkeypatch, "stranger@gmail.com")
    at = AppTest.from_file(APP, default_timeout=30).run()
    text = _text(at) + " ".join(m.value for m in at.markdown)
    assert "No clinic yet" in text
    assert not at.sidebar.selectbox


def test_unverified_google_email_is_refused(two_clinics, monkeypatch):
    from dashboard.auth import Unverified

    def unverified():
        raise Unverified("reception@cure.in")

    monkeypatch.setattr("dashboard.auth.google_email", unverified)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert "Email not verified" in _text(at)
    assert not at.sidebar.selectbox


def test_admin_sees_every_clinic_and_can_give_access(two_clinics, db_url, monkeypatch):
    demo, cure = two_clinics
    signed_in(monkeypatch, "harsh@example.com")
    at = run()
    assert at.sidebar.selectbox[0].options == ["Demo Family Clinic", "Cure Dental Clinic"]
    assert "New clinic" in [b.label for b in at.sidebar.button]
    at.switch_page("views/setup.py").run()
    assert "Team" in [t.label for t in at.tabs]
    next(t for t in at.text_input if t.label == "Google account email").input("Doctor@Demo.in")
    next(b for b in at.button if b.label == "Give access").click().run()
    assert not at.exception
    with sessions(db_url)() as s:
        assert repo.clinic_ids_for_email(s, "doctor@demo.in") == {demo}


def test_viewer_may_open_only_its_clinics():
    from dashboard.auth import Viewer

    member = Viewer(email="r@cure.in", is_admin=False, clinic_ids=frozenset({2}))
    assert member.may_open(2) and not member.may_open(1)
    assert Viewer(email="h@x.in", is_admin=True, clinic_ids=frozenset()).may_open(1)


def test_no_pages_folder():
    # Streamlit auto-lists a folder named pages/ next to app.py whenever app.py
    # stops before st.navigation (the sign-in gate) and runs those files
    # without app.py: a signed-out visitor could open /setup directly.
    assert not (Path(APP).parent / "pages").exists()


# ---------- doctors' hours ----------

def _add_doctor(at, name, starting=None):
    [t for t in at.text_input if t.label == "Name"][-1].input(name)
    if starting:
        next(sb for sb in at.selectbox if sb.label == "Starting hours").select(starting)
    next(b for b in reversed(at.button) if b.label == "Add doctor").click().run()
    assert not at.exception


def _hours(url, clinic_id, name):
    with sessions(url)() as s:
        doctor = next(d for d in repo.get_clinic(s, clinic_id).doctors if d.name == name)
        return sorted((h.weekday, h.start.strftime("%H:%M"), h.end.strftime("%H:%M")) for h in doctor.hours)


def test_a_new_doctor_starts_with_common_hours(seeded):
    url, clinic_id = seeded
    _add_doctor(setup_page(), "Dr. Neha Kulkarni")
    hours = _hours(url, clinic_id, "Dr. Neha Kulkarni")
    assert hours == sorted([(d, "10:00", "13:00") for d in range(6)] + [(d, "17:00", "20:00") for d in range(6)])


def test_a_new_doctor_can_copy_a_colleague_or_start_empty(seeded):
    url, clinic_id = seeded
    _add_doctor(setup_page(), "Dr. Copy", starting="Same as Dr. Rohan Iyer")
    assert _hours(url, clinic_id, "Dr. Copy") == _hours(url, clinic_id, "Dr. Rohan Iyer")
    _add_doctor(setup_page(), "Dr. Empty", starting="No hours yet")
    assert _hours(url, clinic_id, "Dr. Empty") == []


def _hours_tab(url, clinic_id, name="Dr. Asha Mehta"):
    at = setup_page()
    with sessions(url)() as s:
        doctor_id = next(d.id for d in repo.get_clinic(s, clinic_id).doctors if d.name == name)
    at.selectbox(key="hours_doctor").select(doctor_id).run()
    return at, doctor_id


def test_opening_sunday_and_saving(seeded):
    url, clinic_id = seeded
    at, did = _hours_tab(url, clinic_id)
    at.toggle(key=f"hr{did}_6_open").set_value(True).run()
    at.button(key=f"save_hours_{did}").click().run()
    assert not at.exception
    assert (6, "10:00", "13:00") in _hours(url, clinic_id, "Dr. Asha Mehta")


def test_applying_a_pattern_fills_the_week_until_saved(seeded):
    url, clinic_id = seeded
    before = _hours(url, clinic_id, "Dr. Rohan Iyer")
    at, did = _hours_tab(url, clinic_id, "Dr. Rohan Iyer")
    at.selectbox(key=f"pattern_{did}").select("Mon–Fri, 9 am–5 pm").run()
    at.button(key=f"apply_{did}").click().run()
    assert "Unsaved changes" in " ".join(m.value for m in at.markdown)
    assert _hours(url, clinic_id, "Dr. Rohan Iyer") == before  # nothing written yet
    at.button(key=f"save_hours_{did}").click().run()
    assert _hours(url, clinic_id, "Dr. Rohan Iyer") == [(d, "09:00", "17:00") for d in range(5)]


def test_copy_monday_to_open_days(seeded):
    from datetime import time

    url, clinic_id = seeded
    at, did = _hours_tab(url, clinic_id)
    at.time_input(key=f"hr{did}_0_s1").set_value(time(9, 0)).run()
    at.button(key=f"copy_{did}").click().run()
    at.button(key=f"save_hours_{did}").click().run()
    mornings = [h for h in _hours(url, clinic_id, "Dr. Asha Mehta") if h[2] == "13:00"]
    assert mornings == [(d, "09:00", "13:00") for d in range(6)]  # Sunday stays closed


def test_overlapping_sittings_are_explained_not_saved(seeded):
    from datetime import time

    url, clinic_id = seeded
    before = _hours(url, clinic_id, "Dr. Asha Mehta")
    at, did = _hours_tab(url, clinic_id)
    at.time_input(key=f"hr{did}_1_s2").set_value(time(12, 0)).run()  # Tuesday evening starts before 1 pm
    at.button(key=f"save_hours_{did}").click().run()
    assert any("Tuesday: the second sitting starts before the first one ends" in e.value for e in at.error)
    assert _hours(url, clinic_id, "Dr. Asha Mehta") == before


def test_preview_says_what_the_receptionist_will_say(seeded):
    url, clinic_id = seeded
    at, did = _hours_tab(url, clinic_id)
    text = " ".join(m.value for m in at.markdown)
    assert "Monday to Saturday 10:00-13:00 and 17:00-20:00; Sunday not available" in text
