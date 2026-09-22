"""Engine and sessions, built from DATABASE_URL."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from clinic_agent.store import migrations


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///") and not url.endswith(":memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    # pre_ping: a long-running worker's pooled Postgres connections can be
    # dropped by the server; test each before use rather than fail a call.
    engine = create_engine(url, pool_pre_ping=not url.startswith("sqlite"))

    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys unless asked, per connection.
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@lru_cache
def sessions_for(url: str) -> sessionmaker[Session]:
    """One engine per database URL per process, shared by every call.

    Raises migrations.SchemaOutdated if the database isn't at the latest
    schema: running code never migrates (see migrations.py).
    """
    engine = make_engine(url)
    migrations.check(engine)
    return session_factory(engine)
