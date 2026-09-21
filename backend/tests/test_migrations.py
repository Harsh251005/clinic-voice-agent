"""Databases made by the old schema (one patient per phone) are upgraded in place."""

import sqlite3
from datetime import datetime

from clinic_agent.store import repo
from clinic_agent.store.db import init_db, make_engine, session_factory

OLD_SCHEMA = """
CREATE TABLE clinics (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL, address VARCHAR(500) NOT NULL,
  phone VARCHAR(20) NOT NULL, timezone VARCHAR(64) NOT NULL, booking_window_days INTEGER NOT NULL,
  slots_offered INTEGER NOT NULL);
CREATE TABLE doctors (id INTEGER PRIMARY KEY, clinic_id INTEGER NOT NULL REFERENCES clinics (id) ON DELETE CASCADE,
  name VARCHAR(200) NOT NULL, specialty VARCHAR(200) NOT NULL, fee INTEGER NOT NULL, slot_minutes INTEGER NOT NULL,
  active BOOLEAN NOT NULL);
CREATE TABLE patients (id INTEGER NOT NULL, clinic_id INTEGER NOT NULL, name VARCHAR(200) NOT NULL,
  phone VARCHAR(20) NOT NULL, PRIMARY KEY (id), UNIQUE (clinic_id, phone),
  FOREIGN KEY(clinic_id) REFERENCES clinics (id) ON DELETE CASCADE);
CREATE TABLE appointments (id INTEGER PRIMARY KEY, clinic_id INTEGER NOT NULL REFERENCES clinics (id) ON DELETE CASCADE,
  doctor_id INTEGER NOT NULL REFERENCES doctors (id) ON DELETE CASCADE,
  patient_id INTEGER NOT NULL REFERENCES patients (id) ON DELETE CASCADE,
  starts_at DATETIME NOT NULL, ends_at DATETIME NOT NULL, status VARCHAR(20) NOT NULL, source VARCHAR(20) NOT NULL,
  created_at DATETIME NOT NULL);
CREATE UNIQUE INDEX uq_doctor_slot_booked ON appointments (doctor_id, starts_at) WHERE status = 'booked';
INSERT INTO clinics VALUES (1, 'Old Clinic', '', '', 'Asia/Kolkata', 30, 3);
INSERT INTO doctors VALUES (1, 1, 'Dr. Old', '', 500, 15, 1);
INSERT INTO patients VALUES (4, 1, 'Yash', '8928803112');
INSERT INTO appointments VALUES (5, 1, 1, 4, '2026-09-22 11:00:00.000000', '2026-09-22 11:15:00.000000',
  'booked', 'voice', '2026-09-21 10:00:00.000000');
"""


def test_old_database_is_upgraded_keeping_rows_and_a_backup(tmp_path):
    path = tmp_path / "old.db"
    sqlite3.connect(path).executescript(OLD_SCHEMA)

    engine = make_engine(f"sqlite:///{path}")
    init_db(engine)

    assert len(list(tmp_path.glob("old.db.bak-*"))) == 1
    with session_factory(engine)() as s:
        appt = repo.get_appointment(s, 5)
        assert (appt.patient.id, appt.patient.name) == (4, "Yash")  # ids kept, links intact
        # a second family member on the same phone now works
        second = repo.book(s, 1, 1, datetime(2026, 9, 22, 11, 15), "Harsh", "8928803112")
        assert second.patient_id != 4


def test_upgrade_runs_once(tmp_path):
    path = tmp_path / "old.db"
    sqlite3.connect(path).executescript(OLD_SCHEMA)
    engine = make_engine(f"sqlite:///{path}")
    init_db(engine)
    init_db(engine)  # already upgraded: no second rebuild, no second backup
    assert len(list(tmp_path.glob("old.db.bak-*"))) == 1


def test_new_database_needs_no_upgrade(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/new.db")
    init_db(engine)
    assert list(tmp_path.glob("new.db.bak-*")) == []
