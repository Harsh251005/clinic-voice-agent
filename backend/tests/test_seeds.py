"""The demo data stays valid as the schema and rules change: it is what
`docker compose up`, screenshots and demos show."""

from datetime import date, timedelta

from clinic_agent.store import repo
from seeds.demo_day import seed_day


def test_the_demo_day_fills_the_demo_clinic(db):
    s, clinic_id = db
    seed_day(s, clinic_id)
    assert repo.has_calls(s, clinic_id)
    assert len(repo.list_calls(s, clinic_id=clinic_id)) == 2
    week = repo.time_off_overlapping(s, clinic_id, date.today(), date.today() + timedelta(days=7))
    assert sorted(t.doctor_id is None for t in week) == [False, True]  # a doctor's leave and a clinic holiday


def test_the_busy_clinic_seeds_beside_other_clinics_and_costs_nothing(db, monkeypatch):
    # For trying the dashboard under load on a real database: its own clinic,
    # deleted and seeded again any time, and no usage (made-up costs would
    # outlive the clinic).
    from datetime import datetime

    from seeds import busy_clinic

    monkeypatch.setattr(busy_clinic, "DAYS_BACK", 3)  # a short month: the test stays quick
    monkeypatch.setattr(busy_clinic, "DAYS_AHEAD", 2)
    monkeypatch.setattr(busy_clinic, "CALLS", 40)
    s, demo_id = db
    busy_id = busy_clinic.seed_busy(s, member="Owner@Example.com")

    assert busy_id != demo_id and not repo.has_calls(s, demo_id)  # the other clinic is untouched
    clinic = repo.get_clinic(s, busy_id)
    assert clinic.slug == busy_clinic.SLUG and len(clinic.doctors) == 4
    assert all(d.name_hi and d.specialty for d in clinic.doctors)  # no vendor asked for a Hindi name
    assert [m.email for m in repo.list_members(s, busy_id)] == ["owner@example.com"]
    calls = repo.list_calls(s, clinic_id=busy_id, limit=None)
    assert len(calls) == 40 and [c.id for c in calls] == sorted((c.id for c in calls), reverse=True)
    assert [c.started_at for c in calls] == sorted((c.started_at for c in calls), reverse=True)  # arrived in order
    assert not repo.usage_between(s, datetime(2000, 1, 1), datetime(2100, 1, 1))
    assert busy_clinic._existing(s).id == busy_id  # what --replace looks for
