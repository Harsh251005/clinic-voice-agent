"""Clock times as staff read them: "10:30 am", "5 pm". The dashboard is
12-hour throughout, so messages the API passes to staff are too. Callers
hear times through the LLM and spoken.py instead."""

from __future__ import annotations

from datetime import datetime, time


def clock12(at: time | datetime) -> str:
    hour = at.hour % 12 or 12
    suffix = "am" if at.hour < 12 else "pm"
    return f"{hour}:{at.minute:02d} {suffix}" if at.minute else f"{hour} {suffix}"
