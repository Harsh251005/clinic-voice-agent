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
