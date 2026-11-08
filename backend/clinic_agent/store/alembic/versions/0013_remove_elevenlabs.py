"""remove ElevenLabs and the English line from the data (Harsh, 2026-11-08:
Hindi only, "not a trace" of ElevenLabs): its prices, allowance, fees,
bills and usage; every call that ran on it or on the English line, with
its events, transcript, usage and the appointments it booked; problems
about either; "en" in workers' check-ins. Data only, no schema change.

Can't be undone: `python -m clinic_agent.store.migrations` copies a SQLite
file first (Postgres: pg_dump before upgrading). Downgrade keeps the rows gone.

Revision ID: 0013
Revises: 0012
Created: 2026-11-08
"""

from alembic import op
import sqlalchemy as sa


revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None

VENDOR = "elevenlabs"

calls = sa.table("calls", sa.column("id", sa.Integer), sa.column("language", sa.String),
                 sa.column("stack", sa.String), sa.column("appointments", sa.JSON))
heartbeats = sa.table("worker_heartbeats", sa.column("id", sa.Integer), sa.column("languages", sa.String))
incidents = sa.table("incidents", sa.column("kind", sa.String), sa.column("subject", sa.String))
usage = sa.table("usage", sa.column("call_id", sa.Integer), sa.column("provider", sa.String),
                 sa.column("language", sa.String))
appointments = sa.table("appointments", sa.column("id", sa.Integer))
PRICED = [sa.table(name, sa.column("provider", sa.String))
          for name in ("prices", "allowances", "fixed_costs", "vendor_bills")]
CALL_CHILDREN = [sa.table(name, sa.column("call_id", sa.Integer))
                 for name in ("call_events", "call_transcripts", "transcript_access")]


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.select(calls.c.id, calls.c.language, calls.c.stack, calls.c.appointments)).all()
    # Calls from before the language was recorded show the vendor in `stack` only.
    gone = {r.id for r in rows if r.language == "en" or VENDOR in (r.stack or "").lower()}

    def touched(r, actions=None):
        return {a["id"] for a in (r.appointments or []) if actions is None or a.get("action") in actions}

    booked = set().union(*(touched(r, {"booked"}) for r in rows if r.id in gone))
    kept = set().union(*(touched(r) for r in rows if r.id not in gone))  # a later call moved or cancelled it: keep
    if booked - kept:
        conn.execute(appointments.delete().where(appointments.c.id.in_(booked - kept)))

    if gone:  # explicit, not cascades: SQLite revisions run with foreign keys off
        for child in CALL_CHILDREN:
            conn.execute(child.delete().where(child.c.call_id.in_(gone)))
        conn.execute(usage.delete().where(usage.c.call_id.in_(gone)))
        conn.execute(calls.delete().where(calls.c.id.in_(gone)))
    # Usage outlives its call (call_id set to NULL), so it is matched on what it was.
    conn.execute(usage.delete().where(sa.or_(usage.c.provider == VENDOR, usage.c.language == "en")))
    for t in PRICED:
        conn.execute(t.delete().where(t.c.provider == VENDOR))

    conn.execute(incidents.delete().where(sa.or_(
        sa.func.lower(incidents.c.subject).like(f"{VENDOR}%"),  # vendor_errors, price_missing
        sa.and_(incidents.c.kind == "language_off", incidents.c.subject == "en"),
    )))
    for hb in conn.execute(sa.select(heartbeats.c.id, heartbeats.c.languages)).all():
        langs = [x for x in hb.languages.split(",") if x and x != "en"]
        if langs != [x for x in hb.languages.split(",") if x]:
            conn.execute(heartbeats.update().where(heartbeats.c.id == hb.id).values(languages=",".join(langs)))


def downgrade() -> None:
    pass  # deleted rows aren't recreated: restore the backup taken before the upgrade
