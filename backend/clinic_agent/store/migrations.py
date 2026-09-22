"""Schema upgrades, through Alembic.

    uv run python -m clinic_agent.store.migrations    # bring DATABASE_URL to the latest schema

The agent and dashboard never change the schema. They call `check()` and
refuse to start on an old one, so two processes can never migrate the same
database at once. Writing a new revision after changing models.py:

    uv run alembic revision --autogenerate --rev-id 0002 -m "what changed"
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text

logger = logging.getLogger("clinic-agent.migrations")

SCRIPTS = Path(__file__).with_name("alembic")
BASELINE = "0001"
COMMAND = "uv run python -m clinic_agent.store.migrations"


class SchemaOutdated(RuntimeError):
    """The database is not at the schema this code expects."""


def head() -> str:
    return ScriptDirectory.from_config(_config()).get_current_head()


def current(engine: Engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def check(engine: Engine) -> None:
    """Raise SchemaOutdated unless the database is at the latest revision."""
    rev, latest = current(engine), head()
    if rev != latest:
        state = f"at revision {rev}" if rev else "not set up"
        raise SchemaOutdated(
            f"database schema is {state}, this code needs {latest}. Run: {COMMAND}"
        )


def upgrade(engine: Engine) -> None:
    """Bring the database to the latest revision. Safe to run repeatedly."""
    rev = current(engine)
    if rev == head():
        return
    if rev is None and _has_tables(engine):
        _adopt(engine)
    elif rev is not None:
        _backup(engine)
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            # Held until commit: a second upgrade waits instead of racing.
            conn.execute(text("SELECT pg_advisory_xact_lock(7201)"))
        command.upgrade(_config(conn), "head")
    logger.info("database upgraded to %s", head())


def _config(connection=None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(SCRIPTS))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def _has_tables(engine: Engine) -> bool:
    """Any of our tables. An empty alembic_version alone (left by
    `alembic revision --autogenerate` on a fresh database) doesn't count."""
    return bool(set(inspect(engine).get_table_names()) - {"alembic_version"})


def _adopt(engine: Engine) -> None:
    """A database made before Alembic (Stage 2, by create_all): stamp it at
    the baseline, but only if its schema really is the baseline. Stamping a
    different schema would let later revisions run against tables they don't
    expect."""
    if engine.dialect.name != "sqlite":
        raise SchemaOutdated("database has tables but no migration history; refusing to guess")
    baseline = create_engine("sqlite://")
    with baseline.begin() as conn:
        command.upgrade(_config(conn), BASELINE)
    if _shape(engine) != _shape(baseline):
        raise SchemaOutdated(
            f"{engine.url.database} predates migrations and does not match the "
            "baseline schema, so it can't be upgraded automatically"
        )
    _backup(engine)
    with engine.begin() as conn:
        command.stamp(_config(conn), BASELINE)
    logger.info("adopted a pre-Alembic database at revision %s", BASELINE)


def _shape(engine: Engine) -> dict:
    """Tables, columns and uniqueness rules, ignoring constraint names (which
    pre-Alembic databases don't have)."""
    insp = inspect(engine)
    shape = {}
    for table in insp.get_table_names():
        if table == "alembic_version":
            continue
        unique = {tuple(u["column_names"]) for u in insp.get_unique_constraints(table)}
        unique |= {tuple(i["column_names"]) for i in insp.get_indexes(table) if i["unique"]}
        shape[table] = (
            sorted((c["name"], c["nullable"]) for c in insp.get_columns(table)),
            sorted(unique),
        )
    return shape


def _backup(engine: Engine) -> None:
    """Copy a SQLite file before changing it. Postgres is backed up by pg_dump."""
    path = engine.url.database
    if engine.dialect.name != "sqlite" or not path or path == ":memory:":
        return
    src = Path(path)
    dst = src.with_name(f"{src.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(src, dst)
    logger.info("backed up %s to %s before upgrading", src, dst)


if __name__ == "__main__":
    from clinic_agent.config import load_settings
    from clinic_agent.store.db import make_engine

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("alembic").setLevel(logging.WARNING)  # our own lines say what happened
    url = load_settings().database_url
    try:
        upgrade(make_engine(url))
    except SchemaOutdated as err:
        raise SystemExit(f"migration error: {err}") from None
    print(f"{url.split('@')[-1]}: schema at {head()}")
