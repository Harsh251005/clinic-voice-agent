"""In-place upgrades for databases created by an older schema.

A stopgap until Alembic: `create_all` adds missing tables but never changes
existing ones. Each step checks whether it is needed, so running them on
every start is safe. SQLite only - Postgres arrives with Alembic.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, text
from sqlalchemy.schema import CreateTable

from clinic_agent.store.models import Patient

logger = logging.getLogger("clinic-agent.migrations")


def upgrade(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    if _patients_unique_on_phone_only(engine):
        _backup(engine)
        _rebuild_patients(engine)


def _patients_unique_on_phone_only(engine: Engine) -> bool:
    """Old schema: one patient per phone, so a family sharing a phone collided."""
    with engine.connect() as conn:
        if not conn.execute(text("SELECT 1 FROM sqlite_master WHERE name='patients'")).first():
            return False
        for idx in conn.execute(text("PRAGMA index_list('patients')")).mappings():
            if not idx["unique"]:
                continue
            cols = [r["name"] for r in conn.execute(text(f"PRAGMA index_info('{idx['name']}')")).mappings()]
            if cols == ["clinic_id", "phone"]:
                return True
    return False


def _rebuild_patients(engine: Engine) -> None:
    """SQLite can't drop a constraint: copy the table into the new shape.

    The documented 12-step procedure, inside one transaction; row ids are
    kept, so appointments still point at the same patients.
    """
    new_ddl = str(CreateTable(Patient.__table__).compile(engine)).replace(
        "CREATE TABLE patients", "CREATE TABLE patients_new", 1
    )
    with engine.connect() as conn:
        # Must be outside a transaction or SQLite ignores it.
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.commit()
        with conn.begin():
            conn.exec_driver_sql(new_ddl)
            conn.exec_driver_sql(
                "INSERT INTO patients_new (id, clinic_id, name, phone) "
                "SELECT id, clinic_id, name, phone FROM patients"
            )
            conn.exec_driver_sql("DROP TABLE patients")
            conn.exec_driver_sql("ALTER TABLE patients_new RENAME TO patients")
            broken = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if broken:
                raise RuntimeError(f"patients rebuild broke foreign keys: {broken}")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.commit()
    logger.info("upgraded patients: one phone can now hold several patients")


def _backup(engine: Engine) -> None:
    path = engine.url.database
    if not path or path == ":memory:":
        return
    src = Path(path)
    dst = src.with_name(f"{src.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(src, dst)
    logger.info("backed up %s to %s before upgrading", src, dst)
