"""Baseline: the Stage 2 schema (clinics, doctors, hours, leave, FAQ,
patients, appointments).

Databases created before Alembic are stamped at this revision instead of
running it; see `migrations.upgrade`.

Revision ID: 0001
Revises: -
Created: 2026-09-22 12:05:23.234238
"""

from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('clinics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('address', sa.String(length=500), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('booking_window_days', sa.Integer(), nullable=False),
    sa.Column('slots_offered', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_clinics'))
    )
    op.create_table('clinic_faq',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=False),
    sa.Column('question', sa.String(length=300), nullable=False),
    sa.Column('answer', sa.String(length=1000), nullable=False),
    sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], name=op.f('fk_clinic_faq_clinic_id_clinics'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_clinic_faq'))
    )
    op.create_table('doctors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('specialty', sa.String(length=200), nullable=False),
    sa.Column('fee', sa.Integer(), nullable=False),
    sa.Column('slot_minutes', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], name=op.f('fk_doctors_clinic_id_clinics'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_doctors'))
    )
    op.create_table('patients',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], name=op.f('fk_patients_clinic_id_clinics'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_patients')),
    sa.UniqueConstraint('clinic_id', 'phone', 'name', name=op.f('uq_patients_clinic_id_phone_name'))
    )
    op.create_table('appointments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=False),
    sa.Column('doctor_id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('starts_at', sa.DateTime(), nullable=False),
    sa.Column('ends_at', sa.DateTime(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], name=op.f('fk_appointments_clinic_id_clinics'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], name=op.f('fk_appointments_doctor_id_doctors'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], name=op.f('fk_appointments_patient_id_patients'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_appointments'))
    )
    op.create_index('uq_doctor_slot_booked', 'appointments', ['doctor_id', 'starts_at'], unique=True, sqlite_where=sa.text("status = 'booked'"), postgresql_where=sa.text("status = 'booked'"))
    op.create_table('doctor_hours',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('doctor_id', sa.Integer(), nullable=False),
    sa.Column('weekday', sa.Integer(), nullable=False),
    sa.Column('start', sa.Time(), nullable=False),
    sa.Column('end', sa.Time(), nullable=False),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], name=op.f('fk_doctor_hours_doctor_id_doctors'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_doctor_hours'))
    )
    op.create_table('time_off',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=False),
    sa.Column('doctor_id', sa.Integer(), nullable=True),
    sa.Column('date_from', sa.Date(), nullable=False),
    sa.Column('date_to', sa.Date(), nullable=False),
    sa.Column('reason', sa.String(length=200), nullable=False),
    sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], name=op.f('fk_time_off_clinic_id_clinics'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], name=op.f('fk_time_off_doctor_id_doctors'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_time_off'))
    )


def downgrade() -> None:
    op.drop_table('time_off')
    op.drop_table('doctor_hours')
    op.drop_index('uq_doctor_slot_booked', table_name='appointments', sqlite_where=sa.text("status = 'booked'"), postgresql_where=sa.text("status = 'booked'"))
    op.drop_table('appointments')
    op.drop_table('patients')
    op.drop_table('doctors')
    op.drop_table('clinic_faq')
    op.drop_table('clinics')
