"""The agent's instructions, built per call from the clinic's own data.

The persona rules are fixed, one set per language line (Hindi is the only
one: clinic_agent/lines.py); the facts section is generated from the database, so the agent says only what
the clinic entered in the dashboard.
The rules may only describe what is built: never promise an action nothing
performs (checking, holding, taking a message, a callback). When a stage adds
a capability, add it here in the same change.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from clinic_agent.dispatch import Language
from clinic_agent.store.models import Clinic, Doctor, TimeOff

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

HINDI = """
You are the receptionist of {clinic_name}, a clinic in India, on the phone. You are an automated assistant and a woman.

Opening: the call opens with a fixed greeting, already said for you. Never greet again.

Language:
- Always reply in Hindi, to the end of the call, mixing in everyday English words ("अपॉइंटमेंट", "टाइम") the way callers do, even when the caller speaks English. If they ask for English, say kindly that this receptionist speaks Hindi only, and carry on in Hindi.
- Hindi, Hinglish too, wholly in Devanagari, English words included; never Roman letters.
- Everyday spoken Hindi, never bookish: "ज़रा", "खाली है", not "कृपया", "उपलब्ध है".
- About yourself always feminine ("मैं देखती हूँ", "बताती हूँ"). To the caller, respectful "आप" and "जी"; never "sir" or "madam".

Style:
- Under 20 words and one question per reply, except read-backs. Open with a varied acknowledgement ("जी", "अच्छा", "ठीक है"). Never repeat confirmed details.
- Numbers and times in Hindi words. Tools give times like "17:30 (साढ़े पाँच बजे)": say the bracketed words. Phone numbers digit by digit.
- Only "।", "?" and ",": no dashes, brackets or lists.
- Say names as CLINIC FACTS spells them "in Hindi".

Scope: answer only from CLINIC FACTS; book, cancel and move appointments; end the call. No messages, holds, transfers or callbacks. Never guess a name, time, fee or address; never give medical advice. A doctor not in CLINIC FACTS is not at this clinic: say who is.

Tools: before one, say a short line ("एक सेकंड, मैं चेक करती हूँ") and call it in the same reply.

Booking:
1. First ask briefly why they are coming, unless said (don't press). Work out the date from today in CLINIC FACTS. Ask which doctor only if more than one fits and the caller hasn't said. Call find_available_slots; offer only the times it returns; for later ones, call again.
2. Ask the patient's name and ten-digit mobile. Call check_booking (pass the reason in short English), read back what it returns and ask if all is correct. Only after a clear yes, call book_appointment, then confirm once.

Right doctor: match the reason to each specialty. Clearly outside all (fever for an eye specialist): decline kindly, book nothing; suggest a type of doctor only if obvious ("जनरल फ़िज़िशियन"), never one not in CLINIC FACTS, never diagnose. Unsure: book.

Cancel or move: once the caller has given the mobile number and the patient's name, call find_my_appointments; if nothing is found, ask them to check, never hint at other bookings. cancel_appointment and reschedule_appointment only read back at first: call again with the same details after a clear yes.

Ending: when the caller is done, call end_call with a short summary and a warm goodbye, writing nothing else. After just "thanks" or "ok", first ask if there is anything else.

Emergency (chest pain, breathing trouble, heavy bleeding, unconsciousness, seizure, stroke, poisoning, serious injury): tell them at once to call one-zero-eight for an ambulance, or one-one-two, in words.
""".strip()

RULES: dict[Language, str] = {"hi": HINDI}


def build_instructions(clinic: Clinic, time_off: Iterable[TimeOff], now: datetime, language: Language) -> str:
    rules = RULES[language].format(clinic_name=clinic.name)
    return rules + "\n\n" + clinic_facts(clinic, time_off, now, language)


def _named(name: str, name_hi: str, language: Language) -> str:
    """The Hindi line says a name exactly as the clinic spelt it in Hindi."""
    return f"{name} (in Hindi: {name_hi})" if language == "hi" and name_hi else name


_TITLES = ("डॉक्टर", "डॉ.", "डॉ", "dr.", "dr")


def _first_name(name: str) -> tuple[str, str, bool]:
    """(title, first word, more words after it) of a doctor's name."""
    words = name.split()
    title = words.pop(0) if words and words[0].lower() in _TITLES else ""
    return title, (words[0] if words else ""), len(words) > 1


def _doctor_named(name: str, name_hi: str, language: Language, first_names: list[str]) -> str:
    """Harsh, 2026-11-10: the full name every time ("डॉक्टर हर्ष धरनिधरका")
    sounded stiff. Say "डॉक्टर + first name"; the full name only if asked.
    Two doctors sharing a first name keep the full name (no mix-up)."""
    full = _named(name, name_hi, language)
    if language != "hi":
        return full
    spoken = name_hi or name
    _, first, more = _first_name(spoken)
    if not (first and more) or first_names.count(_first_name(name)[1].lower()) > 1:
        return full
    title = "डॉक्टर" if name_hi else "Dr."
    return f'{name} (say "{title} {first}"; the full name only if asked: {spoken})'


def clinic_facts(clinic: Clinic, time_off: Iterable[TimeOff], now: datetime, language: Language) -> str:
    doctors = [d for d in clinic.doctors if d.active]
    names = {d.id: d.name for d in clinic.doctors}
    lines = [
        "CLINIC FACTS (the only facts you may state):",
        f"- Right now it is {now.strftime('%A, %d %B %Y, %H:%M')} at the clinic.",
        f"- Name: {_named(clinic.name, clinic.name_hi, language)}",
    ]
    if clinic.address:
        lines.append(f"- Address: {clinic.address}")
    if clinic.phone:
        lines.append(f"- Phone: {clinic.phone}")

    # Seen 2026-10-24: with one doctor, the agent still asked "which doctor?".
    if len(doctors) == 1:
        lines.append("- Doctor (the clinic's only one, so never ask which doctor):")
    else:
        lines.append(f"- Doctors ({len(doctors)}: ask which one only if the caller hasn't said or described one):"
                     if doctors else "- Doctors: none listed.")
    first_names = [_first_name(d.name)[1].lower() for d in doctors]
    for d in doctors:
        detail = ", ".join(x for x in [d.specialty, f"fee ₹{d.fee}" if d.fee else ""] if x)
        lines.append(f"  - {_doctor_named(d.name, d.name_hi, language, first_names)}{f' ({detail})' if detail else ''}: {weekly_hours(d)}")

    closures = [
        f"  - {names.get(t.doctor_id, 'Whole clinic closed') if t.doctor_id else 'Whole clinic closed'}"
        f"{' on leave' if t.doctor_id else ''}: {_span(t)}{f' ({t.reason})' if t.reason else ''}"
        for t in time_off
    ]
    if closures:
        lines.append("- Upcoming leave and holidays:")
        lines.extend(closures)

    if clinic.faq:
        lines.append("- Other answers the clinic has given:")
        lines.extend(f"  - Q: {f.question} A: {f.answer}" for f in clinic.faq)
    return "\n".join(lines)


def weekly_hours(doctor: Doctor) -> str:
    """'Monday to Saturday 10:00-13:00 and 17:00-20:00; Sunday closed' style."""
    by_day = {
        day: tuple((h.start, h.end) for h in doctor.hours if h.weekday == day)
        for day in range(7)
    }
    if not any(by_day.values()):
        return "no regular hours set"

    groups: list[tuple[list[int], tuple]] = []
    for day in range(7):
        if groups and groups[-1][1] == by_day[day] and groups[-1][0][-1] == day - 1:
            groups[-1][0].append(day)
        else:
            groups.append(([day], by_day[day]))

    parts = []
    for days, sittings in groups:
        label = DAY_NAMES[days[0]] if len(days) == 1 else f"{DAY_NAMES[days[0]]} to {DAY_NAMES[days[-1]]}"
        if sittings:
            times = " and ".join(f"{a:%H:%M}-{b:%H:%M}" for a, b in sittings)
            parts.append(f"{label} {times}")
        else:
            parts.append(f"{label} not available")
    return "; ".join(parts)


def _span(t: TimeOff) -> str:
    if t.date_from == t.date_to:
        return t.date_from.strftime("%A %d %B")
    return f"{t.date_from:%d %B} to {t.date_to:%d %B}"
