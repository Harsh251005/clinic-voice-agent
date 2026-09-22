"""The schema only changes through Alembic, and running code refuses an old one."""

import sqlite3
from datetime import UTC, datetime

import pytest

from clinic_agent.store import migrations, repo
from clinic_agent.store.db import make_engine, session_factory, sessions_for
from clinic_agent.store.models import utc_now

# What Stage 2's create_all made, before Alembic: unnamed constraints.
PRE_ALEMBIC = """
CREATE TABLE clinics (id INTEGER NOT NULL, name VARCHAR(200) NOT NULL, address VARCHAR(500) NOT NULL,
  phone VARCHAR(20) NOT NULL, timezone VARCHAR(64) NOT NULL, booking_window_days INTEGER NOT NULL,
  slots_offered INTEGER NOT NULL, PRIMARY KEY (id));
CREATE TABLE clinic_faq (id INTEGER NOT NULL, clinic_id INTEGER NOT NULL, question VARCHAR(300) NOT NULL,
  answer VARCHAR(1000) NOT NULL, PRIMARY KEY (id), FOREIGN KEY(clinic_id) REFERENCES clinics (id) ON DELETE CASCADE);
CREATE TABLE doctors (id INTEGER NOT NULL, clinic_id INTEGER NOT NULL, name VARCHAR(200) NOT NULL,
  specialty VARCHAR(200) NOT NULL, fee INTEGER NOT NULL, slot_minutes INTEGER NOT NULL, active BOOLEAN NOT NULL,
  PRIMARY KEY (id), FOREIGN KEY(clinic_id) REFERENCES clinics (id) ON DELETE CASCADE);
CREATE TABLE doctor_hours (id INTEGER NOT NULL, doctor_id INTEGER NOT NULL, weekday INTEGER NOT NULL,
  start TIME NOT NULL, "end" TIME NOT NULL, PRIMARY KEY (id),
  FOREIGN KEY(doctor_id) REFERENCES doctors (id) ON DELETE CASCADE);
CREATE TABLE time_off (id INTEGER NOT NULL, clinic_id INTEGER NOT NULL, doctor_id INTEGER, date_from DATE NOT NULL,
  date_to DATE NOT NULL, reason VARCHAR(200) NOT NULL, PRIMARY KEY (id),
  FOREIGN KEY(clinic_id) REFERENCES clinics (id) ON DELETE CASCADE,
  FOREIGN KEY(doctor_id) REFERENCES doctors (id) ON DELETE CASCADE);
CREATE TABLE patients (id INTEGER NOT NULL, clinic_id INTEGER NOT NULL, name VARCHAR(200) NOT NULL,
  phone VARCHAR(20) NOT NULL, PRIMARY KEY (id), UNIQUE (clinic_id, phone, name),
  FOREIGN KEY(clinic_id) REFERENCES clinics (id) ON DELETE CASCADE);
CREATE TABLE appointments (id INTEGER NOT NULL, clinic_id INTEGER NOT NULL, doctor_id INTEGER NOT NULL,
  patient_id INTEGER NOT NULL, starts_at DATETIME NOT NULL, ends_at DATETIME NOT NULL, status VARCHAR(20) NOT NULL,
  source VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL, PRIMARY KEY (id),
  FOREIGN KEY(clinic_id) REFERENCES clinics (id) ON DELETE CASCADE,
  FOREIGN KEY(doctor_id) REFERENCES doctors (id) ON DELETE CASCADE,
  FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE);
CREATE UNIQUE INDEX uq_doctor_slot_booked ON appointments (doctor_id, starts_at) WHERE status = 'booked';
INSERT INTO clinics VALUES (1, 'Cure Dental Clinic', '', '', 'Asia/Kolkata', 30, 3);
INSERT INTO doctors VALUES (1, 1, 'Dr. Khushbu', '', 500, 15, 1);
INSERT INTO patients VALUES (4, 1, 'Harsh', '8928803112');
INSERT INTO appointments VALUES (5, 1, 1, 4, '2026-09-22 11:00:00.000000', '2026-09-22 11:15:00.000000',
  'booked', 'voice', '2026-09-21 10:00:00.000000');
"""


def test_new_database_is_built_to_the_latest_schema(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/new.db")
    migrations.upgrade(engine)
    assert migrations.current(engine) == migrations.head()
    migrations.check(engine)  # does not raise
    assert list(tmp_path.glob("new.db.bak-*")) == []  # nothing to back up


def test_upgrade_is_safe_to_repeat(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/new.db")
    migrations.upgrade(engine)
    migrations.upgrade(engine)
    assert migrations.current(engine) == migrations.head()


def test_empty_version_table_is_still_a_new_database(tmp_path):
    # `alembic revision --autogenerate` leaves this behind on a fresh database.
    path = tmp_path / "new.db"
    sqlite3.connect(path).executescript("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);")
    engine = make_engine(f"sqlite:///{path}")
    migrations.upgrade(engine)
    assert migrations.current(engine) == migrations.head()


def test_running_code_refuses_an_unmigrated_database(tmp_path):
    url = f"sqlite:///{tmp_path}/empty.db"
    with pytest.raises(migrations.SchemaOutdated, match="not set up.*python -m clinic_agent.store.migrations"):
        sessions_for(url)


def test_pre_alembic_database_is_adopted_keeping_rows_and_a_backup(tmp_path):
    path = tmp_path / "clinic.db"
    sqlite3.connect(path).executescript(PRE_ALEMBIC)

    engine = make_engine(f"sqlite:///{path}")
    migrations.upgrade(engine)

    assert migrations.current(engine) == migrations.head()
    assert len(list(tmp_path.glob("clinic.db.bak-*"))) == 1
    with session_factory(engine)() as s:
        appt = repo.get_appointment(s, 5)
        assert (appt.patient.name, appt.doctor.name) == ("Harsh", "Dr. Khushbu")


def test_pre_alembic_database_with_another_schema_is_left_alone(tmp_path):
    # The one-patient-per-phone schema from before 9c5e3f6: stamping it would
    # let later revisions run against tables they don't expect.
    path = tmp_path / "old.db"
    sqlite3.connect(path).executescript(
        PRE_ALEMBIC.replace("UNIQUE (clinic_id, phone, name)", "UNIQUE (clinic_id, phone)")
    )
    engine = make_engine(f"sqlite:///{path}")
    with pytest.raises(migrations.SchemaOutdated, match="does not match the baseline"):
        migrations.upgrade(engine)
    assert migrations.current(engine) is None
    assert list(tmp_path.glob("old.db.bak-*")) == []


def test_record_timestamps_are_utc():
    assert abs(utc_now() - datetime.now(UTC).replace(tzinfo=None)).total_seconds() < 5


def test_models_and_migrations_agree(tmp_path):
    # A models.py change without a matching revision fails here, not in production.
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    from clinic_agent.store.models import Base

    engine = make_engine(f"sqlite:///{tmp_path}/drift.db")
    migrations.upgrade(engine)
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []


def test_existing_clinics_get_unique_slugs(tmp_path):
    from alembic import command

    engine = make_engine(f"sqlite:///{tmp_path}/slugs.db")
    with engine.begin() as conn:
        command.upgrade(migrations._config(conn), "0001")
        for name in ("Cure Dental Clinic", "Cure Dental Clinic", "शर्मा क्लिनिक"):
            conn.exec_driver_sql(
                "INSERT INTO clinics (name, address, phone, timezone, booking_window_days, slots_offered) "
                f"VALUES ('{name}', '', '', 'Asia/Kolkata', 30, 3)"
            )
    migrations.upgrade(engine)
    with session_factory(engine)() as s:
        assert [c.slug for c in repo.list_clinics(s)] == ["cure-dental-clinic", "cure-dental-clinic-2", "clinic"]


def test_foreign_keys_are_back_on_after_an_upgrade(tmp_path):
    # Upgrades switch them off (see _upgrade_sqlite); a pooled connection
    # left that way would silently stop cascading deletes.
    engine = make_engine(f"sqlite:///{tmp_path}/fk.db")
    migrations.upgrade(engine)
    for _ in range(3):
        with engine.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
