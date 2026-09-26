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
