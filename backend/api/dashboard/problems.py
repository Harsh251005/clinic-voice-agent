"""Problems (incidents) for the two dashboards, in two voices.

The clinic reads plain words and what to do about it, never vendor or
server names. The operator (admin) reads what broke and where to look.
Which problems a clinic sees is `incidents.KINDS[kind].clinic_sees`.
"""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request

from api.dashboard import convert, schemas
from api.dashboard.access import Viewer, admin, open_clinic, staff_errors
from clinic_agent import costs, incidents
from clinic_agent.lines import NAMES
from clinic_agent.store import repo
from clinic_agent.store.models import utc_now

router = APIRouter()

HISTORY = timedelta(days=7)  # resolved problems still listed
RANK = {"critical": 0, "warning": 1, "info": 2}

REASONS = {  # why a patient's call page gave up (incidents.CONNECT_FAILURES)
    "mic_blocked": "their browser blocked the microphone",
    "no_mic": "their phone or computer has no microphone",
    "connect_failed": "the call couldn't connect",
    "no_answer": "the receptionist didn't answer",
    "dropped": "the call dropped midway",
}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


VENDORS = {"sarvam": "Sarvam", "openai": "OpenAI", "livekit": "LiveKit"}
# Each part of a call: (the admin's name for it, what the caller notices in plain words).
PARTS = {
    "stt": ("hearing (speech to text)", "hearing callers"),
    "llm": ("thinking (language model)", "answering callers"),
    "tts": ("voice (text to speech)", "speaking to callers"),
}


def _vendor_name(subject: str) -> str:
    """"sarvam/bulbul:v3" -> "Sarvam bulbul:v3"."""
    vendor, _, model = subject.partition("/")
    return f"{VENDORS.get(vendor.lower(), vendor)} {model}".strip()


def _meaning(error: str, vendor: str) -> tuple[str, str]:
    """(what an error means, what to do) from its type and status code, e.g.
    "APIStatusError 402, fatal" -> out of credits, top up."""
    words = error.replace(",", " ").split()
    code = next((int(w) for w in words if w.isdigit() and len(w) == 3), None)
    kind = words[0] if words else ""
    if code in (401, 403):
        return f"its key was rejected ({code})", f"Check the {vendor} API key in backend/.env, then restart the worker."
    if code == 402:
        return "out of credits (402)", f"Top up your {vendor} account."
    if code == 429:
        return "too many requests (429)", f"{vendor} is limiting you: wait a few minutes, or raise your plan's limit."
    if code is not None and code >= 500:
        return f"{vendor}'s own servers are failing ({code})", f"Nothing to fix on your side: check {vendor}'s status page."
    if "Timeout" in kind:
        return "not answering in time", f"Check {vendor}'s status page and this server's internet connection."
    if "Connection" in kind:
        return "can't be reached", f"Check this server's internet connection and {vendor}'s status page."
    return (f"errors ({error})" if error else "errors"), f"Open the errors list for details; check {vendor}'s status page."


def _failed_calls(detail: str) -> tuple[int, list[str]]:
    """(how many, their start times) from "2|3:12 PM,3:20 PM"; an older detail gives (0, [])."""
    n, _, times = detail.partition("|")
    return (int(n), [t for t in times.split(",") if t]) if n.isdigit() else (0, [])


def _when(times: list[str], at: str = "at ") -> str:
    """"at 3:12 PM", "at 3:12 PM and 3:20 PM", "at 3:12 PM, 3:20 PM and 3:41 PM";
    the same minute once; more than three: "between 1:12 PM and 3:40 PM"."""
    unique = list(dict.fromkeys(times))
    if len(unique) > 3:
        return f"between {unique[0]} and {unique[-1]}"
    return at + (unique[0] if len(unique) == 1 else ", ".join(unique[:-1]) + " and " + unique[-1])


def clinic_words(inc: repo.Incident, clinic_id: int) -> tuple[str, str, str | None]:
    """(what's wrong, what to do, where to look) for the clinic's staff."""
    base = f"/clinics/{clinic_id}"
    match inc.kind:
        case "worker_offline":
            return ("Your receptionist is offline. Patients calling now can't reach it.",
                    "ClinicDesk support sees this too. Until it's back, patients can still ring the clinic's own phone.", None)
        case "language_off":
            return ("Patients can't call your receptionist right now.",
                    "ClinicDesk support sees this too.", None)
        case "vendor_errors":
            part = incidents.parse_vendor_detail(inc.detail)[0]
            trouble = PARTS.get(part, ("", "answering calls"))[1]
            return (f"Your receptionist is having trouble {trouble} right now.",
                    "ClinicDesk support sees this too. It clears by itself once calls work again.", None)
        case "calls_failing":
            n, times = _failed_calls(inc.detail)
            when = f" {_when(times)}" if times else " in the last hour"
            return (f"{_plural(n, 'call') if n else 'Several calls'} to your receptionist failed{when}.",
                    "Open Calls to see who called, and ring them back. This clears by itself once a call goes through.",
                    f"{base}/calls")
        case "patients_cant_connect":
            why = REASONS.get(inc.subject, "their call didn't go through")
            return (f"{_plural(inc.count, 'patient')} couldn't reach your receptionist: {why}.",
                    "If it keeps happening, tell ClinicDesk support.", None)
        case "no_doctors":
            return ("Callers can't book: no doctor is taking bookings.",
                    "Add a doctor, or turn one back on, in Clinic settings.", f"{base}/setup?tab=doctors")
        case "doctor_no_hours":
            return (f"Callers can't book {inc.detail}: no weekly hours are set.",
                    "Set their hours in Clinic settings, Weekly hours.", f"{base}/setup?tab=hours")
        case "doctor_no_specialty":
            return (f"{inc.detail} has no specialty, so the receptionist can't tell which visits they see.",
                    "Add their specialty in Clinic settings, Doctors (General Physician counts).",
                    f"{base}/setup?tab=doctors")
        case "clinic_paused":
            return ("Your receptionist is paused by ClinicDesk support. It isn't answering calls.",
                    "Contact ClinicDesk support to turn it back on.", None)
        case "bookings_need_call":
            n = int(inc.detail or 0)
            return (f"{_plural(n, 'upcoming booking')} can't go ahead as booked.",
                    "Call the patients: Today lists them under Needs attention.", f"{base}/today")
    return ("Something needs attention.", "", None)


def admin_words(inc: repo.Incident, clinic: str | None) -> tuple[str, str, str | None]:
    """(what broke, what to do, where to look) for the operator."""
    at = f"{clinic}: " if clinic else ""
    match inc.kind:
        case "worker_offline":
            since = "never checked in" if inc.detail == "never" else f"last checked in {inc.detail}"
            return (f"Receptionist offline: no worker connected to LiveKit ({since}).",
                    "Start or restart the worker: uv run python main.py start", None)
        case "language_off":
            name = NAMES.get(inc.subject, inc.subject)
            return (f"The {name} line is off: the worker started without a key it needs, so it takes no calls.",
                    "Set the missing API key in backend/.env and restart the worker; its log names the key.", None)
        case "vendor_errors":
            part, count, latest = incidents.parse_vendor_detail(inc.detail)
            vendor = VENDORS.get(inc.subject.partition("/")[0].lower(), "the vendor")
            meaning, todo = _meaning(latest, vendor)
            role = f" {PARTS[part][0]}" if part in PARTS else ""
            times = f", {_plural(count, 'error')} in 15 minutes" if count else ""
            return (f"{_vendor_name(inc.subject)}{role}: {meaning}{times}.",
                    f"{todo} Clears by itself once a call shows it working (a test call counts).", "/admin/errors")
        case "calls_failing":
            n, times = _failed_calls(inc.detail)
            when = f" ({_when(times, at='')})" if times else ""
            return (f"{at}{_plural(n, 'call') if n else 'Several calls'} failed or dropped{when}.",
                    "Open the calls' traces. Clears by itself once a call there ends well (a test call counts).",
                    f"/admin/calls?clinic={inc.clinic_id}")
        case "patients_cant_connect":
            return (f"{at}{_plural(inc.count, 'patient')} couldn't connect ({inc.subject}).",
                    "Check the call page, LiveKit and the worker.", None)
        case "server_error":
            return (f"Server error: {inc.subject}, {_plural(inc.count, 'time')}.",
                    "See the API log for the traceback. Clears by itself once that page works again.", None)
        case "livekit_minutes":
            return (f"LiveKit minutes: {inc.detail}.",
                    "Upgrade the LiveKit plan or self-host before calls are refused.", None)
        case "hindi_names_failing":
            return (f"{at}Hindi name suggestions are failing ({inc.subject}), {_plural(inc.count, 'time')}.",
                    "Names save without one and the Hindi line spells them itself. Check OPENAI_API_KEY and the API log.", None)
        case "price_missing":
            if inc.subject == "rate":
                return (f"Costs are incomplete: no dollar-to-rupee rate covers {inc.detail}.",
                        "Add a rate from that date in Costs, Prices.", "/admin/costs/prices")
            provider, model, unit = (inc.subject.split("/") + ["", "", ""])[:3]
            words = costs.UNITS.get(unit, unit)
            add = urlencode({"add": inc.subject, "from": inc.detail})
            return (f"Costs are incomplete: {VENDORS.get(provider, provider)} {model} has no price for {words} (used since {inc.detail}).",
                    "Open fills in the missing price for you: type the amount from the vendor's pricing page.",
                    f"/admin/costs/prices?{add}")
        case "voice_clip_failed":
            return (f"Recording a voice clip failed ({inc.detail}), {_plural(inc.count, 'time')}.",
                    "Calls say those phrases live meanwhile. Try Record again; if it keeps failing, check the "
                    "voice vendor's status and credits.", "/admin/voice")
        case "phrase_translation_failing":
            return (f"Turning a phrase into Hindi failed, {_plural(inc.count, 'time')} ({inc.detail}).",
                    "Type the Hindi yourself on Voice & phrases, or try again. Check OPENAI_API_KEY and the API log.",
                    "/admin/voice")
        case "voice_clips_unread":
            return (f"{at}A call could not read its fixed phrases ({inc.detail}), {_plural(inc.count, 'time')}.",
                    "Those calls said the greeting, fillers and goodbyes live, in the built-in words (any edited "
                    "wording was not used). Check the worker log and the database.", None)
        case "purge_failed":
            return ("Deleting expired transcripts failed.",
                    "Transcripts older than 30 days may still be stored: check the API log.", None)
    # The clinic-side problems read the same for the operator, with the clinic named.
    title, action, _ = clinic_words(inc, inc.clinic_id or 0)
    return (f"{at}{title}", action, f"/admin/clinics/{inc.clinic_id}" if inc.clinic_id else None)


def _problem(inc: repo.Incident, words: tuple[str, str, str | None], seen, clinic_name: str | None = None,
             can_mark_seen: bool = True) -> schemas.Problem:
    title, action, link = words
    return schemas.Problem(
        id=inc.id, kind=inc.kind, severity=inc.severity, title=title, action=action, link=link,
        clinic_id=inc.clinic_id, clinic_name=clinic_name, count=inc.count,
        since=convert.utc(inc.opened_at), last_seen=convert.utc(inc.last_seen_at),
        resolved_at=convert.utc(inc.resolved_at), resolved_how=inc.resolved_how or ("fixed" if inc.resolved_at else ""),
        seen=seen is not None, can_mark_seen=can_mark_seen and inc.severity != "critical",
    )


def _split(problems: list[schemas.Problem]) -> schemas.Problems:
    open_ = sorted((p for p in problems if p.resolved_at is None), key=lambda p: (RANK[p.severity], -p.since.timestamp()))
    return schemas.Problems(open=open_, recent=[p for p in problems if p.resolved_at is not None])


@router.get("/api/clinics/{clinic_id}/problems", response_model=schemas.Problems)
def clinic_problems(request: Request, clinic_id: int = Depends(open_clinic)):
    with request.app.state.sessions() as s:
        rows = repo.list_incidents(s, since=utc_now() - HISTORY, clinic_id=clinic_id)
        return _split([
            # A system-wide problem (a vendor failing) stays up for the clinic until it's fixed.
            _problem(i, clinic_words(i, clinic_id), i.seen_by_clinic_at, can_mark_seen=i.clinic_id is not None)
            for i in rows if incidents.clinic_sees(i.kind)
        ])


@router.post("/api/clinics/{clinic_id}/problems/{problem_id}/seen", response_model=schemas.Problem)
def clinic_seen(problem_id: int, request: Request, clinic_id: int = Depends(open_clinic)):
    """Only the clinic's own problems: a system-wide one (receptionist
    offline) stays up until it's fixed."""
    with staff_errors(), request.app.state.sessions() as s:
        inc = repo.in_clinic(s, repo.Incident, problem_id, clinic_id)
        if not incidents.clinic_sees(inc.kind):
            raise repo.NotFound(problem_id)
        inc = repo.mark_incident_seen(s, inc.id, "clinic", utc_now())
        return _problem(inc, clinic_words(inc, clinic_id), inc.seen_by_clinic_at, can_mark_seen=True)


@router.get("/api/admin/problems", response_model=schemas.Problems)
def admin_problems(request: Request, _viewer: Viewer = Depends(admin)):
    with request.app.state.sessions() as s:
        names = {c.id: c.name for c in repo.list_clinics(s)}
        rows = repo.list_incidents(s, since=utc_now() - HISTORY)
        return _split([
            _problem(i, admin_words(i, names.get(i.clinic_id)), i.seen_by_admin_at, names.get(i.clinic_id))
            for i in rows
        ])


@router.post("/api/admin/problems/{problem_id}/seen", response_model=schemas.Problem)
def admin_seen(problem_id: int, request: Request, _viewer: Viewer = Depends(admin)):
    with staff_errors(), request.app.state.sessions() as s:
        inc = repo.mark_incident_seen(s, problem_id, "admin", utc_now())
        name = repo.get_clinic(s, inc.clinic_id).name if inc.clinic_id else None
        return _problem(inc, admin_words(inc, name), inc.seen_by_admin_at, name)
