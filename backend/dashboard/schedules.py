"""Common weekly schedules, so a doctor's hours start filled in and staff only
adjust them. A sitting is (weekday 0=Mon..6=Sun, start, end)."""

from __future__ import annotations

from datetime import time

MORNING = (time(10, 0), time(13, 0))
EVENING = (time(17, 0), time(20, 0))
MON_TO_SAT = range(6)

PRESETS: dict[str, list[tuple[int, time, time]]] = {
    "Mon–Sat, 10 am–1 pm and 5–8 pm": [(d, *s) for d in MON_TO_SAT for s in (MORNING, EVENING)],
    "Mon–Sat, 10 am–1 pm": [(d, *MORNING) for d in MON_TO_SAT],
    "Mon–Sat, 5–8 pm": [(d, *EVENING) for d in MON_TO_SAT],
    "Mon–Fri, 9 am–5 pm": [(d, time(9, 0), time(17, 0)) for d in range(5)],
}
DEFAULT = "Mon–Sat, 10 am–1 pm and 5–8 pm"
NONE = "No hours yet"


def same_as(doctor) -> list[tuple[int, time, time]]:
    return [(h.weekday, h.start, h.end) for h in doctor.hours]
