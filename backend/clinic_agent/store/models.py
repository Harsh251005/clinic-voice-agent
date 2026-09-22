"""Tables. Every row belongs to a clinic, directly or through its doctor.

Appointment times are naive and in the clinic's own timezone
(`Clinic.timezone`); every clinic today is in India, and a naive local time is
what staff and callers mean by "eleven o'clock". Record-keeping timestamps
(`created_at`) are naive UTC.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import ForeignKey, Index, MetaData, String, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    # Named constraints, so a later migration can find and change them;
    # Alembic can't reliably alter an unnamed one (SQLite especially).
    metadata = MetaData(naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


def utc_now() -> datetime:
    """Naive UTC. Record-keeping timestamps are UTC, not the server's clock:
    a server in UTC would otherwise file them 5.5 hours off India time."""
    return datetime.now(UTC).replace(tzinfo=None)


class Clinic(Base):
    __tablename__ = "clinics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # Public name in the clinic's call link (/call/<slug>): the link, not the
    # database id, is what patients see. Set by repo.create_clinic.
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    address: Mapped[str] = mapped_column(String(500), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    booking_window_days: Mapped[int] = mapped_column(default=30)
    slots_offered: Mapped[int] = mapped_column(default=3)

    doctors: Mapped[list[Doctor]] = relationship(
        back_populates="clinic", cascade="all, delete-orphan", order_by="Doctor.id"
    )
    faq: Mapped[list[ClinicFaq]] = relationship(
        cascade="all, delete-orphan", order_by="ClinicFaq.id"
    )


class ClinicFaq(Base):
    __tablename__ = "clinic_faq"

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(String(300))
    answer: Mapped[str] = mapped_column(String(1000))


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    specialty: Mapped[str] = mapped_column(String(200), default="")
    fee: Mapped[int] = mapped_column(default=0)  # rupees
    slot_minutes: Mapped[int] = mapped_column(default=15)
    active: Mapped[bool] = mapped_column(default=True)

    clinic: Mapped[Clinic] = relationship(back_populates="doctors")
    hours: Mapped[list[DoctorHours]] = relationship(
        cascade="all, delete-orphan",
        order_by="(DoctorHours.weekday, DoctorHours.start)",
    )


class DoctorHours(Base):
    """One sitting. Several rows per weekday give split shifts."""

    __tablename__ = "doctor_hours"

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    weekday: Mapped[int]  # 0 = Monday ... 6 = Sunday
    start: Mapped[time]
    end: Mapped[time]


class TimeOff(Base):
    """Leave (doctor_id set) or a whole-clinic holiday (doctor_id null)."""

    __tablename__ = "time_off"

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"))
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), default=None
    )
    date_from: Mapped[date]
    date_to: Mapped[date]
    reason: Mapped[str] = mapped_column(String(200), default="")


class Patient(Base):
    """A person, identified by phone number *and* name: one phone is often
    shared by a family (a parent booking for their children)."""

    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("clinic_id", "phone", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        # The database, not the code, guarantees one booking per doctor per
        # slot. Cancelled rows are excluded so a freed slot can be rebooked.
        Index(
            "uq_doctor_slot_booked",
            "doctor_id",
            "starts_at",
            unique=True,
            sqlite_where=text("status = 'booked'"),
            postgresql_where=text("status = 'booked'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(20), default="booked")  # booked | cancelled
    source: Mapped[str] = mapped_column(String(20), default="voice")  # voice | dashboard
    created_at: Mapped[datetime] = mapped_column(default=utc_now)  # UTC

    doctor: Mapped[Doctor] = relationship()
    patient: Mapped[Patient] = relationship()
