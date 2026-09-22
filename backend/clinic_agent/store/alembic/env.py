"""Alembic environment: runs revisions against a connection.

`migrations.upgrade()` hands in its own connection; the `alembic` CLI (used
to write new revisions) gets one built from DATABASE_URL.
"""

from alembic import context

from clinic_agent.store.models import Base


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        # SQLite can't ALTER most things; batch mode rebuilds the table instead.
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("offline (--sql) mode is not supported; run against a database")

connection = context.config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    from clinic_agent.config import load_settings
    from clinic_agent.store.db import make_engine

    with make_engine(load_settings().database_url).begin() as conn:
        _run(conn)
