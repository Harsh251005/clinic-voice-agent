"""What the dashboard API sends and accepts. The Next.js app's TypeScript
types are generated from these (via FastAPI's OpenAPI schema), so a change
here shows up as a type error in the frontend, not a broken screen."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ClinicSummary(BaseModel):
    id: int
    name: str
    slug: str
    staff: bool  # this viewer may see its patients (appointments, calls)


class Me(BaseModel):
    email: str  # "" when sign-in is off
    is_admin: bool
    login: Literal["google", "off"]
    clinics: list[ClinicSummary]  # the ones this viewer may open


class Sitting(BaseModel):
    weekday: int = Field(ge=0, le=6)  # 0 = Monday
    start: time
    end: time


class Doctor(BaseModel):
    id: int
    name: str
    specialty: str
    fee: int
    slot_minutes: int
    active: bool
    hours: list[Sitting]
    hours_text: str  # how the receptionist describes them
    upcoming: int  # booked appointments from now on


class Faq(BaseModel):
    id: int
    question: str
    answer: str


class TimeOff(BaseModel):
    id: int
    date_from: date
    date_to: date
    doctor_id: int | None  # None = the whole clinic
    reason: str


class Clinic(BaseModel):
    id: int
    name: str
    slug: str
    call_link: str
    address: str
    phone: str
    timezone: str
    booking_window_days: int
    slots_offered: int
    doctors: list[Doctor]
    faq: list[Faq]
    time_off: list[TimeOff]  # today onwards, in the clinic's timezone


class NewClinic(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=20)


class ClinicDetails(NewClinic):
    booking_window_days: int = Field(ge=1, le=365)
    slots_offered: int = Field(ge=1, le=6)


class SlugIn(BaseModel):
    slug: str


class DoctorIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    specialty: str = Field(default="", max_length=200)
    fee: int = Field(ge=0)
    slot_minutes: int = Field(ge=5, le=120)


class NewDoctor(DoctorIn):
    hours: list[Sitting] = []  # starting hours, e.g. a pattern


class DoctorPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    specialty: str | None = Field(default=None, max_length=200)
    fee: int | None = Field(default=None, ge=0)
    slot_minutes: int | None = Field(default=None, ge=5, le=120)
    active: bool | None = None


class HoursIn(BaseModel):
    sittings: list[Sitting]


class HoursText(BaseModel):
    text: str


class Pattern(BaseModel):
    name: str
    sittings: list[Sitting]


class TimeOffIn(BaseModel):
    date_from: date
    date_to: date
    doctor_id: int | None = None
    reason: str = Field(default="", max_length=200)


class FaqIn(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=1000)


class Member(BaseModel):
    id: int
    email: str


class MemberIn(BaseModel):
    email: str


class Appointment(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    patient_name: str
    patient_phone: str
    starts_at: datetime
    ends_at: datetime
    status: Literal["booked", "cancelled"]
    source: Literal["voice", "dashboard"]
    reason: str  # why the patient is coming; "" if not given
    # Why a booking can't go ahead as booked (leave, holiday, hours changed,
    # doctor inactive): staff should call the patient. None when it's fine.
    problem: str | None = None


class AppointmentIn(BaseModel):
    """A booking as staff enter it; also the whole edit form (PUT)."""
    doctor_id: int
    starts_at: datetime  # clinic-local, no timezone: "2026-12-07T10:05:00"
    patient_name: str = Field(min_length=1, max_length=200)
    patient_phone: str = Field(max_length=20)
    reason: str = Field(default="", max_length=300)

    @field_validator("starts_at")
    @classmethod
    def _clinic_local(cls, v: datetime) -> datetime:
        if v.tzinfo is not None:
            raise ValueError("send the clinic's local time, without a timezone")
        return v.replace(second=0, microsecond=0)


class FreeTimes(BaseModel):
    times: list[time]  # the doctor's free slots that day, as quick picks


class TimeOffAdded(TimeOff):
    clashes: list[Appointment]  # upcoming bookings on those days, to call about


class Day(BaseModel):
    day: date
    appointments: list[Appointment]
    booked: int  # this day
    booked_on_calls: int  # this day, by the receptionist
    next_7_days: int  # booked, this day and the six after


class Error(BaseModel):
    error: str


# ---------- calls (trace: no words from the call) ----------

class CallChange(BaseModel):
    id: int  # appointment
    action: Literal["booked", "moved", "cancelled"]


class CallSummary(BaseModel):
    id: int
    clinic_id: int
    clinic_name: str
    started_at: datetime  # UTC, with offset
    duration_s: int | None  # None while live or never finished
    # live: still going; ended; dropped: never finished (worker crashed or was killed)
    status: Literal["live", "ended", "dropped"]
    end_reason: str
    outcome: str
    stack: str
    turn_count: int
    error_count: int
    tool_failures: int
    appointments: list[CallChange]


class TraceEvent(BaseModel):
    t_ms: int
    kind: str  # stt | eou | llm | tts | reply | tool | error
    name: str
    duration_ms: int | None
    ok: bool
    detail: str


class TranscriptAccess(BaseModel):
    email: str
    reason: str
    at: datetime  # UTC, with offset


class CallTrace(CallSummary):
    events: list[TraceEvent]
    transcript_kept: bool  # False once deleted after the retention period
    accesses: list[TranscriptAccess]


class TranscriptItem(BaseModel):
    t_ms: int
    role: Literal["caller", "agent", "tool", "error"]
    text: str
    tool: str | None = None
    ok: bool | None = None
    args: str | None = None  # the tool's arguments as the model sent them (JSON)
    interrupted: bool = False


class TranscriptReason(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


# ---------- admin panel ----------

class Stage(BaseModel):
    stage: str  # stt | eou | llm | tts | reply
    stack: str
    count: int
    p50_ms: int
    p95_ms: int


class VendorErrors(BaseModel):
    name: str  # provider/model
    errors: int
    calls: int  # calls with at least one error from it


class Attention(BaseModel):
    kind: Literal["dropped", "failed", "errors", "quiet"]
    text: str
    call_id: int | None = None
    clinic_id: int | None = None


class Health(BaseModel):
    days: int
    calls: int
    calls_today: int
    outcomes: dict[str, int]
    dropped: int
    with_errors: int
    stages: list[Stage]
    vendors: list[VendorErrors]
    attention: list[Attention]


class ErrorGroup(BaseModel):
    name: str
    detail: str
    count: int
    last_at: datetime  # UTC, with offset
    call_ids: list[int]  # the latest few


class AdminClinic(BaseModel):
    id: int
    name: str
    slug: str
    active: bool
    doctors: int
    members: list[Member]
    calls_7d: int
    calls_with_errors_7d: int
    last_call_at: datetime | None


class ActiveIn(BaseModel):
    active: bool


class DeleteClinicIn(BaseModel):
    confirm_name: str
