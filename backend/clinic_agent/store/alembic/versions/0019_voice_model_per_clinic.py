"""voice model per clinic: set beside the speaker, since a speaker only exists in some models

Revision ID: 0019
Revises: 0018
Created: 2026-11-10 17:00:00

Found 2026-11-10: with the model shared and the speaker per clinic, moving
to a new model needed both changed at once on two pages. Each clinic takes
the shared value it had.
"""

from alembic import op
import sqlalchemy as sa


revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tts_model', sa.String(length=100), server_default='', nullable=False))
    op.execute("UPDATE clinics SET tts_model = COALESCE((SELECT sarvam_tts_model FROM system_settings WHERE id = 1), '')")
    with op.batch_alter_table('system_settings', schema=None) as batch_op:
        batch_op.drop_column('sarvam_tts_model')


def downgrade() -> None:
    with op.batch_alter_table('system_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sarvam_tts_model', sa.String(length=100), server_default='', nullable=False))
    op.execute("UPDATE system_settings SET sarvam_tts_model = COALESCE((SELECT tts_model FROM clinics ORDER BY id LIMIT 1), '')")
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.drop_column('tts_model')
