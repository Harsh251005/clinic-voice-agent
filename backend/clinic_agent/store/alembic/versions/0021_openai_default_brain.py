"""the brain a new install starts on: OpenAI

Revision ID: 0021
Revises: 0020
Created: 2026-11-13 20:30:00

Harsh, 2026-11-13: after hearing both on real calls, OpenAI's gpt-4.1-mini
is the default brain from now on. Only a new install changes: one that has
taken a call, or copied its brain from an old .env, keeps what it runs on.
(Migration 0018 makes the settings row, so a new install already has one
by now: "no call yet" is what tells it apart.)
"""

from alembic import op
import sqlalchemy as sa


revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def _default(vendor: str) -> None:
    with op.batch_alter_table('system_settings', schema=None) as batch_op:
        batch_op.alter_column(
            'hindi_llm', existing_type=sa.String(length=20), existing_nullable=False, server_default=vendor)


def upgrade() -> None:
    _default('openai')
    op.execute(
        "UPDATE system_settings SET hindi_llm = 'openai' "
        "WHERE copied_from_env = false AND NOT EXISTS (SELECT 1 FROM calls)"
    )


def downgrade() -> None:
    _default('sarvam')
