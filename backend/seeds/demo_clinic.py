"""A fictional clinic for tests and a first run. Real clinics use the dashboard.

    uv run python -m seeds.demo_clinic     # seed the DATABASE_URL database
"""

from __future__ import annotations

from datetime import time

from clinic_agent.store import repo
from clinic_agent.store.db import Session

MORNING = (time(10, 0), time(13, 0))
EVENING = (time(17, 0), time(20, 0))
MON_TO_SAT = range(6)


def seed_demo(s: Session) -> int:
    """Create the demo clinic and return its id."""
    clinic = repo.create_clinic(
        s,
        name="Demo Family Clinic",
        address="Shop 4, Sunrise Apartments, Borivali East, Mumbai",
        phone="02212345678",
    )
    general = repo.add_doctor(
        s, clinic.id, name="Dr. Asha Mehta", specialty="General Physician",
        fee=500, slot_minutes=15,
    )
    repo.set_doctor_hours(
        s, general.id,
        [(d, *MORNING) for d in MON_TO_SAT] + [(d, *EVENING) for d in MON_TO_SAT],
    )
    child = repo.add_doctor(
        s, clinic.id, name="Dr. Rohan Iyer", specialty="Paediatrician",
        fee=700, slot_minutes=20,
    )
    repo.set_doctor_hours(s, child.id, [(d, time(11, 0), time(14, 0)) for d in (0, 2, 4)])
    repo.add_faq(s, clinic.id, "Is there parking?", "Two-wheeler parking only, in front of the building.")
    repo.add_faq(s, clinic.id, "How can I pay?", "Cash, UPI and cards are accepted.")
    return clinic.id


if __name__ == "__main__":
    from clinic_agent.config import load_settings
    from clinic_agent.store import migrations
    from clinic_agent.store.db import make_engine, session_factory

    cfg = load_settings()
    engine = make_engine(cfg.database_url)
    migrations.upgrade(engine)
    with session_factory(engine)() as s:
        if repo.list_clinics(s):
            raise SystemExit("database already has a clinic; not seeding")
        print(f"seeded demo clinic id={seed_demo(s)} into {cfg.database_url}")
