"""What the dashboard API sends and accepts. The Next.js app's TypeScript
types are generated from these (via FastAPI's OpenAPI schema), so a change
here shows up as a type error in the frontend, not a broken screen."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError


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


_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def hindi_name(value: str | None) -> str | None:
    """A name as the Hindi receptionist says it: Devanagari only, or blank."""
    if value is None:
        return None
    value = " ".join(value.split())
    if value and (not _DEVANAGARI.search(value) or re.search(r"[A-Za-z]", value)):
        # A custom error: its message reaches staff as written, without pydantic's "Value error," prefix.
        raise PydanticCustomError("hindi_name", "Write it in Hindi letters (Devanagari), for example डॉक्टर आशा मेहता.")
    return value


def required_specialty(value: str | None) -> str | None:
    """Never blank, not even spaces: the receptionist matches reasons to it."""
    if value is None:
        return None
    value = " ".join(value.split())
    if not value:
        raise PydanticCustomError(
            "specialty", "Add the doctor's specialty, for example General Physician or Eye Specialist.")
    return value


class Doctor(BaseModel):
    id: int
    name: str
    name_hi: str  # how the Hindi receptionist says it; "" = its own way
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
    name_hi: str  # how the Hindi receptionist says it; "" = its own way
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
    has_calls: bool  # the receptionist has taken at least one call (a test call counts)


class NewClinic(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=20)


class ClinicDetails(NewClinic):
    booking_window_days: int = Field(ge=1, le=365)
    slots_offered: int = Field(ge=1, le=6)
    name_hi: str | None = Field(default=None, max_length=200)  # None: left as it is

    @field_validator("name_hi")
    @classmethod
    def _hindi(cls, value: str | None) -> str | None:
        return hindi_name(value)


class NameIn(BaseModel):
    name: str = Field(max_length=200)


class HindiName(BaseModel):
    name_hi: str


class SlugIn(BaseModel):
    slug: str


class DoctorIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    name_hi: str = Field(default="", max_length=200)

    @field_validator("name_hi")
    @classmethod
    def _hindi(cls, value: str | None) -> str | None:
        return hindi_name(value)
    # Required (Harsh, 2026-11-09), "General Physician" included: the receptionist
    # matches each caller's reason to it before booking.
    specialty: str = Field(min_length=1, max_length=200)

    @field_validator("specialty")
    @classmethod
    def _specialty(cls, value: str | None) -> str | None:
        return required_specialty(value)
    fee: int = Field(ge=0)
    slot_minutes: int = Field(ge=5, le=120)


class NewDoctor(DoctorIn):
    hours: list[Sitting] = []  # starting hours, e.g. a pattern


class DoctorPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    name_hi: str | None = Field(default=None, max_length=200)

    @field_validator("name_hi")
    @classmethod
    def _hindi(cls, value: str | None) -> str | None:
        return hindi_name(value)
    specialty: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("specialty")
    @classmethod
    def _specialty(cls, value: str | None) -> str | None:
        return required_specialty(value)
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


Visit = Literal["arrived", "done", "no_show"]


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
    visit: Visit | None = None  # what happened at the clinic, as staff marked it
    reason: str  # why the patient is coming; "" if not given
    # The receptionist couldn't tell whether the reason fits the doctor: check it.
    reason_unsure: bool = False
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


class Span(BaseModel):
    start: time
    end: time


class DoctorDay(BaseModel):
    """One diary column: what the doctor's day looks like."""
    id: int
    name: str
    slot_minutes: int
    active: bool
    sittings: list[Span]  # working hours that weekday; empty = doesn't sit
    off: str | None  # "On leave", "Clinic closed: Diwali"; None when in
    free: list[time]  # bookable slots left (none before now, none when off)


class Day(BaseModel):
    day: date
    appointments: list[Appointment]
    # Active doctors, and inactive ones only when they have bookings that day.
    doctors: list[DoctorDay]
    booked: int  # this day
    booked_on_calls: int  # this day, by the receptionist
    next_7_days: int  # booked, this day and the six after


class WeekDoctorDay(BaseModel):
    doctor_id: int
    sits: bool  # has working hours that weekday
    off: str | None
    free: int  # bookable slots left


class WeekDay(BaseModel):
    day: date
    appointments: list[Appointment]  # booked only
    doctors: list[WeekDoctorDay]


class DoctorRef(BaseModel):
    id: int
    name: str


class Week(BaseModel):
    start: date
    doctors: list[DoctorRef]
    days: list[WeekDay]  # seven, from start


class VisitIn(BaseModel):
    visit: Visit | None  # None clears the mark


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
    language: Literal["hi", ""]  # the call's line; "" for calls from before it was recorded
    test: bool  # staff calling from the dashboard, not a patient
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
    cost: CallCost | None = None  # None for calls from before costs were tracked


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


# ---------- a clinic's own calls ----------

class ClinicCallChange(BaseModel):
    """An appointment a call made, moved or cancelled, as staff read it.
    Details are None when the appointment was deleted since."""
    action: Literal["booked", "moved", "cancelled"]
    appointment_id: int
    patient_name: str | None
    doctor_name: str | None
    starts_at: datetime | None  # clinic-local


class ClinicCall(BaseModel):
    id: int
    started_at: datetime  # UTC, with offset
    duration_s: int | None
    status: Literal["live", "ended", "dropped"]
    outcome: str
    language: Literal["hi", ""]  # the call's line; "" for calls from before it was recorded
    test: bool  # staff's own test call from the dashboard: erasable, left out of the counts
    changes: list[ClinicCallChange]


class TestCalls(BaseModel):
    """The clinic's own test calls still on record (Talk to receptionist)."""
    count: int  # all of them
    erasable: int  # finished: a call still going can't be erased yet


class TestCallsErased(BaseModel):
    erased: int


class TestCallPass(BaseModel):
    """Join a LiveKit room as the caller; the clinic's receptionist is sent in."""
    url: str
    token: str
    room: str


class SpokenLine(BaseModel):
    """One thing said on a call. Only the caller and the receptionist: the
    tools it used and vendor errors stay in the operator's trace."""
    t_ms: int
    role: Literal["caller", "agent"]
    text: str
    interrupted: bool = False


class SupportView(BaseModel):
    """ClinicDesk support opened this call's transcript, and why."""
    reason: str
    at: datetime  # UTC, with offset


class CallsToday(BaseModel):
    """Today in the clinic's timezone: how busy the receptionist was, and the
    calls where the caller may not have been helped (cut off or failed)."""
    calls: int
    changed: int  # calls that booked, moved or cancelled something
    questions: int  # calls that only asked something
    unhelped: list[ClinicCall]


class ClinicCallDetail(ClinicCall):
    transcript_kept: bool  # False once deleted after the retention period
    conversation: list[SpokenLine]
    support_views: list[SupportView]


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


# ---------- problems (incidents): no patient data ----------

class Problem(BaseModel):
    id: int
    kind: str
    severity: Literal["critical", "warning", "info"]
    title: str  # what's wrong, in the reader's words (clinic: plain; admin: technical)
    action: str  # what to do about it; "" if nothing
    link: str | None  # a dashboard path to look at
    clinic_id: int | None  # None: the whole system
    clinic_name: str | None  # admin only
    count: int  # times it happened while open
    since: datetime
    last_seen: datetime
    resolved_at: datetime | None
    # "fixed": shown working again; "quiet": nothing new for a while and nothing
    # retried it (last happened at last_seen); "" while open, or closed before this was kept
    resolved_how: Literal["", "fixed", "quiet"]
    seen: bool  # acknowledged on this side
    can_mark_seen: bool  # False: urgent, or (for a clinic) system-wide: it stays up until fixed


class Problems(BaseModel):
    open: list[Problem]  # worst first
    recent: list[Problem]  # resolved in the last 7 days, newest first


# ---------- costs (admin) ----------

Provider = Literal["sarvam", "openai", "livekit"]
Unit = Literal["tokens_in", "tokens_cached", "tokens_out", "seconds_heard", "characters", "minutes"]
Currency = Literal["INR", "USD"]
Part = Literal["listening", "thinking", "speaking", "call_line", "other"]
MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"


class CostLine(BaseModel):
    """One vendor's part of a call (or of another cost), priced."""
    part: Part
    provider: str
    model: str
    unit: str
    unit_label: str  # "seconds heard"
    quantity: float
    rupees: float | None  # None: no price (or no dollar rate) for it on that day
    price: str  # "₹30 per 3,600 seconds heard", "" when missing
    missing: Literal["", "price", "rate"]


class CallCost(BaseModel):
    call_id: int | None  # None once the call itself was erased (a test call) or purged
    clinic_id: int | None
    clinic_name: str
    started_at: datetime
    language: Literal["hi", ""]
    test: bool
    rupees: float  # what could be priced
    complete: bool  # every part had a price
    parts: dict[str, float]  # part -> rupees
    lines: list[CostLine]


class CostSlice(BaseModel):
    key: str
    label: str
    rupees: float
    calls: int = 0


class CostDay(BaseModel):
    day: date
    rupees: float


class FreeUse(BaseModel):
    provider: str
    unit_label: str
    allowance: float
    used: float
    rupees: float  # what the free part would have cost


class FixedUse(BaseModel):
    name: str
    provider: str
    rupees: float | None


class MissingPrice(BaseModel):
    why: Literal["price", "rate"]
    provider: str
    model: str
    unit_label: str


class BillCheck(BaseModel):
    provider: str
    currency: str
    ours: float | None  # None: part of it couldn't be priced
    theirs: float
    note: str


class CostMonth(BaseModel):
    month: str
    months: list[str]  # with usage, newest first (always includes this month)
    tracked_since: datetime | None
    usage_rupees: float
    free_rupees: float
    fixed_rupees: float
    to_pay_rupees: float
    calls: int
    test_calls: int
    per_call_rupees: float | None
    other_rupees: float
    by_language: list[CostSlice]
    by_part: list[CostSlice]
    by_vendor: list[CostSlice]
    by_clinic: list[CostSlice]
    by_day: list[CostDay]
    free: list[FreeUse]
    fixed: list[FixedUse]
    missing: list[MissingPrice]
    bills: list[BillCheck]
    top_calls: list[CallCost]  # most expensive first


class PriceIn(BaseModel):
    provider: Provider
    model: str = Field(default="", max_length=100)  # "" = every model of the vendor without its own price
    unit: Unit
    amount: float = Field(ge=0)
    per: float = Field(gt=0)
    currency: Currency
    valid_from: date
    note: str = Field(default="", max_length=300)


class PriceRow(PriceIn):
    id: int


class ModelPricesIn(BaseModel):
    """A language model's three token prices, per million tokens, saved as one.
    `replace`: the price rows this takes the place of (a correction); empty
    adds them (a new price from a date)."""
    provider: Provider
    model: str = Field(default="", max_length=100)
    currency: Currency
    valid_from: date
    note: str = Field(default="", max_length=300)
    tokens_in: float = Field(ge=0)
    tokens_cached: float = Field(ge=0)
    tokens_out: float = Field(ge=0)
    replace: list[int] = Field(default_factory=list, max_length=10)


class RateIn(BaseModel):
    valid_from: date
    inr_per_usd: float = Field(gt=0)
    note: str = Field(default="", max_length=300)


class RateRow(RateIn):
    id: int


class AllowanceIn(BaseModel):
    provider: Provider
    unit: Unit
    quantity: float = Field(ge=0)
    valid_from: date
    note: str = Field(default="", max_length=300)


class AllowanceRow(AllowanceIn):
    id: int


class FixedIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: Provider
    amount: float = Field(ge=0)
    currency: Currency
    valid_from: date
    valid_to: date | None = None


class FixedRow(FixedIn):
    id: int


class BillIn(BaseModel):
    month: str = Field(pattern=MONTH)
    provider: Provider
    amount: float = Field(ge=0)
    currency: Currency
    note: str = Field(default="", max_length=300)


class BillRow(BillIn):
    id: int


class UsedKind(BaseModel):
    """What calls were counted in: a price must name this vendor, model and unit
    (or leave the model blank) to cover them."""
    provider: str
    model: str
    unit: str
    first_used: date
    last_used: date


class CostSettings(BaseModel):
    prices: list[PriceRow]
    rates: list[RateRow]
    allowances: list[AllowanceRow]
    fixed: list[FixedRow]
    bills: list[BillRow]
    units: dict[str, str]  # unit -> plain words
    used: list[UsedKind]
    counted_in: dict[str, list[str]]  # vendor -> the units its calls are counted in: a price in another can't match


# ---------- voice & phrases (admin) ----------

PhraseKind = Literal["greeting", "filler", "goodbye_fallback", "goodbye_time_limit"]


class VoiceOut(BaseModel):
    """The voice calls use now: recordings are kept per voice."""
    vendor: str
    model: str
    voice: str
    pace: float | None
    pitch: float | None
    sample_rate: int


class Take(BaseModel):
    """A phrase as one clinic's calls say it (the shared greeting names each
    clinic, so it has one take per clinic; every other phrase has one)."""
    clinic_id: int | None
    clinic_name: str  # "" for a phrase every clinic shares
    spoken: str  # the exact words said, {clinic} filled in
    key: str | None  # its recording's name for the current voice; None without a voice
    recorded_at: datetime | None  # None: not recorded for this voice and these words
    duration_s: float | None
    live_pace: float | None  # the live voice's speed on the calls it serves (to flag a different recording speed)


class PhraseOut(BaseModel):
    id: int
    kind: PhraseKind
    language: Literal["hi"]
    slot: int
    clinic_id: int | None  # a clinic's own greeting; None for the shared phrases
    clinic_name: str
    source: str  # the English the admin wrote
    text: str  # the Hindi that is spoken
    pace: float  # how fast its recording is spoken (apart from the live voice)
    takes: list[Take]


class VoiceClinic(BaseModel):
    id: int
    name: str
    spoken_name: str
    own_greeting: bool


class VoicePage(BaseModel):
    voice: VoiceOut | None
    voice_problem: str  # why there is no voice (no key...); "" when there is one
    voices_differ: bool  # clinics have different voices: shared lines are recorded once per voice
    rupees_per_1000_chars: float | None  # the voice's price today; None when no price is set
    max_chars: int
    pace_min: float  # the speeds a recording may have
    pace_max: float
    phrases: list[PhraseOut]
    clinics: list[VoiceClinic]


class PaceIn(BaseModel):
    pace: float


class PhraseIn(BaseModel):
    source: str = Field(max_length=500)
    text: str = Field(max_length=500)


class TranslateIn(BaseModel):
    english: str = Field(max_length=500)
    clinic_id: int | None = None  # spell the words this clinic already spells (its names)


class Translated(BaseModel):
    text: str


class TakeRef(BaseModel):
    phrase_id: int
    clinic_id: int | None = None  # which clinic's take of the shared greeting


class RecordIn(BaseModel):
    takes: list[TakeRef] = Field(min_length=1, max_length=50)


class RecordOut(BaseModel):
    recorded: int
    failed: str  # "" when every take was recorded; else why it stopped
    page: VoicePage


# ---------- Admin > Receptionist (clinic_agent/receptionist_settings.py SYSTEM) ----------

class Limit(BaseModel):
    low: float | None
    high: float | None
    default: float | None


class SystemSettingsBase(BaseModel):
    rules: str  # "" = the default rules (default_rules)
    hindi_llm: Literal["sarvam", "openai"]
    sarvam_llm_model: str
    openai_llm_model: str
    sarvam_stt_model: str
    sarvam_stt_language: str
    sarvam_stt_mode: str
    sarvam_tts_model: str
    min_endpointing_delay: float
    number_endpointing_delay: float
    interrupt_min_speech: float
    vad_min_silence: float
    greeting_interruptible: bool


class SystemSettingsOut(SystemSettingsBase):
    default_rules: str  # the rules in code, used while `rules` is blank
    rules_max_words: int
    blank_means: dict[str, str]  # what a blank text field uses: the vendor's own default
    limits: dict[str, Limit]  # each number's allowed range and default
    llm_vendors: list[str]


class SystemSettingsIn(BaseModel):
    """Any of the fields; only those sent change."""
    rules: str | None = Field(default=None, max_length=10_000)
    hindi_llm: Literal["sarvam", "openai"] | None = None
    sarvam_llm_model: str | None = Field(default=None, max_length=100)
    openai_llm_model: str | None = Field(default=None, max_length=100)
    sarvam_stt_model: str | None = Field(default=None, max_length=100)
    sarvam_stt_language: str | None = Field(default=None, max_length=20)
    sarvam_stt_mode: str | None = Field(default=None, max_length=30)
    sarvam_tts_model: str | None = Field(default=None, max_length=100)
    min_endpointing_delay: float | None = None
    number_endpointing_delay: float | None = None
    interrupt_min_speech: float | None = None
    vad_min_silence: float | None = None
    greeting_interruptible: bool | None = None


# ---------- a clinic's Receptionist tab (receptionist_settings.CLINIC), admins only ----------

class ClinicReceptionistOut(BaseModel):
    clinic_id: int
    clinic_name: str
    instructions: str  # added after the main rules on this clinic's calls
    directions: str  # said when a caller asks the way
    tts_speaker: str  # "" = speaker_default
    tts_pace: float  # live voice speed
    tts_pitch: float | None  # None = the voice's own
    max_call_minutes: float
    speaker_default: str
    instructions_max_words: int
    directions_max_chars: int
    limits: dict[str, Limit]


class ClinicReceptionistIn(BaseModel):
    """Any of the fields; only those sent change. tts_pitch null = the voice's own."""
    instructions: str | None = Field(default=None, max_length=5_000)
    directions: str | None = Field(default=None, max_length=1_000)
    tts_speaker: str | None = Field(default=None, max_length=50)
    tts_pace: float | None = None
    tts_pitch: float | None = None
    max_call_minutes: float | None = None


class VoiceImpact(BaseModel):
    lines: int  # the lines this clinic's calls say
    recorded_now: int  # recorded in its current voice
    recorded_after: int  # recorded in the voice being tried out


class Admins(BaseModel):
    emails: list[str]  # ADMIN_EMAILS: see every clinic, including patients' transcripts (each opening logged)
    sign_in: str  # "google" or "off" (local development: everyone is an admin)
