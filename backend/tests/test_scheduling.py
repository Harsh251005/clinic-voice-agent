from datetime import date, datetime, time

import pytest

from clinic_agent.scheduling import NotBookable, check_bookable_day, free_slots, is_off

DAY = date(2026, 9, 22)  # a Tuesday
EARLY = datetime(2026, 9, 21, 9, 0)  # the day before: nothing is in the past
SPLIT = [(time(10), time(13)), (time(17), time(20))]


def at(h, m=0):
    return datetime(2026, 9, 22, h, m)


def test_slots_fill_each_sitting_and_fit_inside_it():
    slots = free_slots(DAY, [(time(10), time(11))], 20, [], EARLY)
    # 10:40-11:00 fits; 11:00 would end past the sitting
    assert slots == [at(10), at(10, 20), at(10, 40)]


def test_split_shift_has_no_slots_in_the_gap():
    slots = free_slots(DAY, SPLIT, 60, [], EARLY)
    assert slots == [at(10), at(11), at(12), at(17), at(18), at(19)]


def test_booked_slot_is_excluded():
    slots = free_slots(DAY, [(time(10), time(11))], 15, [(at(10, 15), at(10, 30))], EARLY)
    assert slots == [at(10), at(10, 30), at(10, 45)]


def test_overlap_after_slot_length_change_is_excluded():
    # booked when slots were 15 min; now 20 min, so 10:00-10:20 overlaps 10:15-10:30
    slots = free_slots(DAY, [(time(10), time(11))], 20, [(at(10, 15), at(10, 30))], EARLY)
    assert slots == [at(10, 40)]


def test_past_and_too_soon_slots_are_excluded():
    now = at(10, 5)
    slots = free_slots(DAY, [(time(10), time(11))], 15, [], now, lead_minutes=30)
    assert slots == [at(10, 45)]  # 10:30 starts only 25 min from now


def test_part_of_day_filter():
    assert free_slots(DAY, SPLIT, 60, [], EARLY, part_of_day="evening") == [at(17), at(18), at(19)]
    assert free_slots(DAY, SPLIT, 60, [], EARLY, part_of_day="afternoon") == [at(12)]
    with pytest.raises(ValueError):
        free_slots(DAY, SPLIT, 60, [], EARLY, part_of_day="night")


def test_no_sittings_no_slots():
    assert free_slots(DAY, [], 15, [], EARLY) == []


def test_unsorted_sittings_come_out_in_order():
    slots = free_slots(DAY, list(reversed(SPLIT)), 180, [], EARLY)
    assert slots == [at(10), at(17)]


def test_leave_and_clinic_holiday():
    off = [(7, date(2026, 9, 21), date(2026, 9, 23)), (None, date(2026, 10, 2), date(2026, 10, 2))]
    assert is_off(DAY, 7, off)
    assert not is_off(DAY, 8, off)
    assert is_off(date(2026, 10, 2), 8, off)  # whole clinic closed


def test_bookable_day_window():
    today = date(2026, 9, 21)
    check_bookable_day(today, today, 30)
    check_bookable_day(date(2026, 10, 21), today, 30)
    with pytest.raises(NotBookable, match="in the past"):
        check_bookable_day(date(2026, 9, 20), today, 30)
    with pytest.raises(NotBookable, match="30 days ahead"):
        check_bookable_day(date(2026, 10, 22), today, 30)
