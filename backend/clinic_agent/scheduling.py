"""Which appointment slots are free. Pure functions: no database, no LiveKit.

Everything here takes plain values so each rule is unit-testable on its own;
the booking tool gathers the inputs from `store.repo` and calls in.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta

# Where a slot's start time falls, for "subah" / "shaam" style requests.
PARTS_OF_DAY = {
    "morning": (time(0), time(12)),
    "afternoon": (time(12), time(17)),
    "evening": (time(17), time.max),
}


class NotBookable(ValueError):
    """The requested day can't be booked; the message says why, for the caller."""


def check_bookable_day(day: date, today: date, window_days: int) -> None:
    if day < today:
        raise NotBookable(f"{day.isoformat()} is in the past")
    if day > today + timedelta(days=window_days):
        raise NotBookable(
            f"bookings open only {window_days} days ahead, up to "
            f"{(today + timedelta(days=window_days)).isoformat()}"
        )


def is_off(
    day: date,
    doctor_id: int,
    time_off: Iterable[tuple[int | None, date, date]],
) -> bool:
    """True if the doctor is on leave or the whole clinic is closed that day.

    `time_off` rows are (doctor_id or None for the whole clinic, from, to).
    """
    return any(
        (who is None or who == doctor_id) and start <= day <= end
        for who, start, end in time_off
    )


def free_slots(
    day: date,
    sittings: Iterable[tuple[time, time]],
    slot_minutes: int,
    booked: Iterable[tuple[datetime, datetime]],
    now: datetime,
    lead_minutes: int = 30,
    part_of_day: str | None = None,
) -> list[datetime]:
    """Start times of free slots on `day`, earliest first.

    A slot must fit wholly inside a sitting, must not overlap any booked
    (start, end) range, and must start at least `lead_minutes` after `now`
    so nobody is booked into a slot that begins while they are still on
    the phone.
    """
    if slot_minutes <= 0:
        raise ValueError("slot_minutes must be positive")
    if part_of_day is not None and part_of_day not in PARTS_OF_DAY:
        raise ValueError(f"part_of_day must be one of {sorted(PARTS_OF_DAY)}")

    length = timedelta(minutes=slot_minutes)
    earliest = now + timedelta(minutes=lead_minutes)
    booked = list(booked)
    window = PARTS_OF_DAY.get(part_of_day or "")

    slots = []
    for start_t, end_t in sorted(sittings):
        start = datetime.combine(day, start_t)
        end = datetime.combine(day, end_t)
        while start + length <= end:
            if (
                start >= earliest
                and not any(start < b_end and b_start < start + length for b_start, b_end in booked)
                and (window is None or window[0] <= start.time() < window[1])
            ):
                slots.append(start)
            start += length
    return slots
