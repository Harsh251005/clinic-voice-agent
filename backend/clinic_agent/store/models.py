"""Tables. Every row belongs to a clinic, directly or through its doctor.

Appointment times are naive and in the clinic's own timezone
(`Clinic.timezone`); every clinic today is in India, and a naive local time is
what staff and callers mean by "eleven o'clock". Record-keeping timestamps
(`created_at`, call times) are naive UTC.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import JSON, ForeignKey, Index, MetaData, String, UniqueConstraint, text
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
    # Paused by the operator (admin panel): the call page says the clinic isn't
    # taking calls and the worker refuses its calls. Nothing else changes.
    active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    doctors: Mapped[list[Doctor]] = relationship(
        back_populates="clinic", cascade="all, delete-orphan", order_by="Doctor.id"
    )
    faq: Mapped[list[ClinicFaq]] = relationship(
        cascade="all, delete-orphan", order_by="ClinicFaq.id"
    )


class ClinicMember(Base):
    """A Google account (by email) that may open this clinic in the dashboard.
    Emails are stored lowercased. Admins (ADMIN_EMAILS) see every clinic
    without rows here."""

    __tablename__ = "clinic_members"
    __table_args__ = (UniqueConstraint("clinic_id", "email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(254))
    added_at: Mapped[datetime] = mapped_column(default=utc_now)  # UTC


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
    # Why the patient is coming, in the caller's or staff's words ("आँखों से
    # धुंधला दिखता है"). Health information: shown to the clinic, never logged.
    reason: Mapped[str] = mapped_column(String(300), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)  # UTC

    doctor: Mapped[Doctor] = relationship()
    patient: Mapped[Patient] = relationship()


# ---------- calls ----------
#
# A call is kept as two kinds of data, and the split is the privacy line:
# the trace (Call + CallEvent) says what happened - timings, tool names,
# errors, outcome - and never what anyone said, so the operator may always
# see it. The transcript (CallTranscript) is what was said: patient data,
# for the clinic, and for the operator only through a logged opening
# (TranscriptAccess). No audio is ever stored.


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (Index("ix_calls_clinic_id_started_at", "clinic_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"))
    room: Mapped[str] = mapped_column(String(128), default="")
    started_at: Mapped[datetime] = mapped_column(default=utc_now)  # UTC
    # Null until the worker finishes the call: a row left open after the
    # time limit is a call the worker never finished (it crashed or stopped).
    ended_at: Mapped[datetime | None] = mapped_column(default=None)  # UTC
    # caller_left | agent_ended | time_limit | shutdown | error
    end_reason: Mapped[str] = mapped_column(String(20), default="")
    # booked | moved | cancelled | info_only | no_action | failed
    outcome: Mapped[str] = mapped_column(String(20), default="")
    stack: Mapped[str] = mapped_column(String(300), default="")  # provider/model for STT, LLM, TTS: which took each turn
    turn_count: Mapped[int] = mapped_column(default=0)  # times the caller spoke
    error_count: Mapped[int] = mapped_column(default=0)  # vendor (STT/LLM/TTS) errors
    # What the call changed: [{"id": 12, "action": "booked"}, ...]
    appointments: Mapped[list] = mapped_column(JSON, default=list)


class CallEvent(Base):
    """One step of a call's trace. Never content: `detail` is a code or a
    count (an error's type and status), not words from the call."""

    __tablename__ = "call_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    t_ms: Mapped[int]  # since the call started
    kind: Mapped[str] = mapped_column(String(10))  # stt | eou | llm | tts | reply | tool | error
    name: Mapped[str] = mapped_column(String(100), default="")  # the tool, or the failing provider/model
    duration_ms: Mapped[int | None] = mapped_column(default=None)
    ok: Mapped[bool] = mapped_column(default=True)
    detail: Mapped[str] = mapped_column(String(200), default="")


class CallTranscript(Base):
    """What was said on a call. Its own table, so no trace query can read
    it by accident. Deleted after the retention period (store/purge.py)."""

    __tablename__ = "call_transcripts"

    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), primary_key=True)
    # [{"t_ms": 0, "role": "agent" | "caller" | "tool", "text": ..., ...}]
    items: Mapped[list] = mapped_column(JSON, default=list)
    purge_after: Mapped[datetime]  # UTC


class TranscriptAccess(Base):
    """The operator opened a clinic's call transcript, and why. Shown to the
    clinic, so reading one is never silent."""

    __tablename__ = "transcript_access"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(254))
    reason: Mapped[str] = mapped_column(String(300))
    at: Mapped[datetime] = mapped_column(default=utc_now)  # UTC
