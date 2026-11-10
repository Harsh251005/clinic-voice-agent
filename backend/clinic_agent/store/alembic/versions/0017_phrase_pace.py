"""phrase pace: each recorded phrase has its own speed, apart from the live voice

Revision ID: 0017
Revises: 0016
Created: 2026-11-10 15:00:00

Existing phrases start at 0.9: the speed the live voice had when they were
recorded (Harsh, 2026-11-09), so those recordings keep playing after the
live voice moved to 0.95.
"""

from alembic import op
import sqlalchemy as sa


revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('phrases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pace', sa.Double(), server_default=sa.text('1.0'), nullable=False))
    op.execute("UPDATE phrases SET pace = 0.9")


def downgrade() -> None:
    with op.batch_alter_table('phrases', schema=None) as batch_op:
        batch_op.drop_column('pace')
