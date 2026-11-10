"""receptionist settings: what every clinic shares (system_settings) and what each clinic sets

Revision ID: 0018
Revises: 0017
Created: 2026-11-10 16:00:00

Harsh, 2026-11-10: everything configurable from the admin. Defaults match
the code's; `python -m clinic_agent.store.migrations` then copies the old
.env values in once (clinic_agent/receptionist_settings.py).
"""

from alembic import op
import sqlalchemy as sa


revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    settings = op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rules', sa.Text(), server_default='', nullable=False),
        sa.Column('hindi_llm', sa.String(length=20), server_default='sarvam', nullable=False),
        sa.Column('sarvam_llm_model', sa.String(length=100), server_default='', nullable=False),
        sa.Column('openai_llm_model', sa.String(length=100), server_default='', nullable=False),
        sa.Column('sarvam_stt_model', sa.String(length=100), server_default='', nullable=False),
        sa.Column('sarvam_stt_language', sa.String(length=20), server_default='', nullable=False),
        sa.Column('sarvam_stt_mode', sa.String(length=30), server_default='transcribe', nullable=False),
        sa.Column('sarvam_tts_model', sa.String(length=100), server_default='', nullable=False),
        sa.Column('min_endpointing_delay', sa.Double(), server_default='0.2', nullable=False),
        sa.Column('number_endpointing_delay', sa.Double(), server_default='1.5', nullable=False),
        sa.Column('interrupt_min_speech', sa.Double(), server_default='0.3', nullable=False),
        sa.Column('vad_min_silence', sa.Double(), server_default='0.6', nullable=False),
        sa.Column('greeting_interruptible', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('copied_from_env', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_system_settings')),
    )
    op.bulk_insert(settings, [{'id': 1}])
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.add_column(sa.Column('instructions', sa.Text(), server_default='', nullable=False))
        batch_op.add_column(sa.Column('directions', sa.String(length=300), server_default='', nullable=False))
        batch_op.add_column(sa.Column('tts_speaker', sa.String(length=50), server_default='', nullable=False))
        batch_op.add_column(sa.Column('tts_pace', sa.Double(), server_default='1.0', nullable=False))
        batch_op.add_column(sa.Column('tts_pitch', sa.Double(), nullable=True))
        batch_op.add_column(sa.Column('max_call_minutes', sa.Double(), server_default='10.0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        for name in ('max_call_minutes', 'tts_pitch', 'tts_pace', 'tts_speaker', 'directions', 'instructions'):
            batch_op.drop_column(name)
    op.drop_table('system_settings')
