"""reason unsure: the receptionist booked but couldn't tell if the reason fits the doctor

Revision ID: 0016
Revises: 0015
Created: 2026-11-09 18:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('appointments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reason_unsure', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('appointments', schema=None) as batch_op:
        batch_op.drop_column('reason_unsure')
