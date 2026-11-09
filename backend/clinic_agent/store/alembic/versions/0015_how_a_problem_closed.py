"""how a problem closed: fixed, or quiet (nothing new and nothing retried it)

Revision ID: 0015
Revises: 0014
Created: 2026-11-09 16:24:46.715454
"""

from alembic import op
import sqlalchemy as sa


revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('resolved_how', sa.String(length=10), server_default='', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.drop_column('resolved_how')
