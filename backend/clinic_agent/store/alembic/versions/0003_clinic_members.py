"""Clinic members: which Google accounts (by email) may open a clinic in the
dashboard.

Revision ID: 0003
Revises: 0002
Created: 2026-09-22 14:41:50.762596
"""

from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('clinic_members',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('added_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], name=op.f('fk_clinic_members_clinic_id_clinics'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_clinic_members')),
    sa.UniqueConstraint('clinic_id', 'email', name=op.f('uq_clinic_members_clinic_id_email'))
    )


def downgrade() -> None:
    op.drop_table('clinic_members')
