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
INSERT INTO patients VALUES (4, 1, 'Harsh', '9876503112');
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


def test_elevenlabs_and_the_english_line_leave_no_trace(tmp_path):
    # 0013 (Harsh, 2026-11-08): Hindi only. Calls that ran on ElevenLabs go,
    # with everything tied to them; Hindi calls and their costs stay.
    from datetime import date

    from alembic import command
    from sqlalchemy import func, select, text

    from clinic_agent.store import models as m

    engine = make_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        command.upgrade(migrations._config(conn), "0012")  # 0013 changes no schema: today's models fit (bar incidents, below)
    now = utc_now()
    with session_factory(engine)() as s:
        clinic = m.Clinic(name="Cure", slug="cure")
        s.add(clinic)
        s.flush()
        doctor = m.Doctor(clinic_id=clinic.id, name="Dr. A")
        patient = m.Patient(clinic_id=clinic.id, name="Harsh", phone="9876503112")
        s.add_all([doctor, patient])
        s.flush()

        def appt(hour):
            a = m.Appointment(clinic_id=clinic.id, doctor_id=doctor.id, patient_id=patient.id,
                              starts_at=datetime(2026, 10, 13, hour), ends_at=datetime(2026, 10, 13, hour, 30))
            s.add(a)
            s.flush()
            return a.id

        english_booked, moved_later, hindi_booked = appt(10), appt(11), appt(12)

        def call(language, stack, booked=()):
            c = m.Call(clinic_id=clinic.id, room="r", started_at=now, language=language, stack=stack,
                       appointments=[{"id": i, "action": a} for i, a in booked])
            s.add(c)
            s.flush()
            s.add_all([m.CallEvent(call_id=c.id, t_ms=0, kind="error", name=stack.split(" ")[0], ok=False),
                       m.CallTranscript(call_id=c.id, items=[], purge_after=now)])
            s.add(m.Usage(at=now, clinic_id=clinic.id, call_id=c.id, language=language, source="call",
                          part="thinking", provider="openai", model="gpt-4.1-mini", unit="tokens_in", quantity=1))
            return c.id

        call("en", "elevenlabs/scribe_v2_medical · openai/gpt-4.1-mini",
             [(english_booked, "booked"), (moved_later, "booked")])
        call("", "elevenlabs/scribe_v2 · openai/gpt-6-luna")  # before calls had a language
        hindi = call("hi", "sarvam/saaras:v3 · sarvam/sarvam-105b · sarvam/bulbul:v3",
                     [(moved_later, "moved"), (hindi_booked, "booked")])
        s.add_all([
            m.Usage(at=now, language="en", source="call", part="speaking", provider="elevenlabs",
                    model="eleven_v3", unit="characters", quantity=9),  # its call already deleted
            m.FixedCost(name="Starter", provider="elevenlabs", amount=5, currency="USD", valid_from=date(2026, 10, 1)),
            m.WorkerHeartbeat(worker="AW_1", host="h", languages="en,hi", started_at=now, last_seen=now),
        ])
        # Written as 0012 had them: resolved_how (0015) did not exist yet.
        for key, kind, subject, severity in [("a", "vendor_errors", "ElevenLabs/eleven_v3", "warning"),
                                             ("b", "language_off", "en", "warning"), ("c", "language_off", "hi", "critical")]:
            s.execute(text("INSERT INTO incidents (key, kind, subject, clinic_id, severity, detail, count, opened_at, last_seen_at)"
                           " VALUES (:key, :kind, :subject, NULL, :severity, '', 1, :now, :now)"),
                      {"key": key, "kind": kind, "subject": subject, "severity": severity, "now": now.isoformat(" ")})
        s.commit()

    migrations.upgrade(engine)

    with session_factory(engine)() as s:
        assert s.scalars(select(m.Call.id)).all() == [hindi]
        for model in (m.CallEvent, m.CallTranscript, m.Usage):
            assert s.scalars(select(model.call_id)).all() == [hindi]
        assert s.scalars(select(m.Appointment.id).order_by(m.Appointment.id)).all() == [moved_later, hindi_booked]
        for model in (m.Price, m.Allowance, m.FixedCost, m.VendorBill, m.Usage):
            assert s.scalar(select(func.count()).where(model.provider == "elevenlabs")) == 0
        assert s.scalar(select(func.count()).select_from(m.Price)) == 18  # the other seeded prices stay
        assert s.scalars(select(m.Incident.subject)).all() == ["hi"]
        assert s.scalar(select(m.WorkerHeartbeat.languages)) == "hi"
