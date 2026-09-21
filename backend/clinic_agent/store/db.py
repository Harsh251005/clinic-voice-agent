"""Engine and sessions, built from DATABASE_URL."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from clinic_agent.store.models import Base


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///") and not url.endswith(":memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url)

    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys unless asked, per connection.
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def init_db(engine: Engine) -> None:
    """Create missing tables. Replaced by migrations before real clinic data."""
    Base.metadata.create_all(engine)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@lru_cache
def sessions_for(url: str) -> sessionmaker[Session]:
    """One engine per database URL per process, shared by every call."""
    engine = make_engine(url)
    init_db(engine)
    return session_factory(engine)
