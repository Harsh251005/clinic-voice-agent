from datetime import date, datetime, time

import pytest

from clinic_agent.store import repo


def test_demo_clinic_loads_with_doctors_hours_and_faq(db):
    s, clinic_id = db
    clinic = repo.get_clinic(s, clinic_id)
    assert clinic.name == "Demo Family Clinic"
    assert [d.name for d in clinic.doctors] == ["Dr. Asha Mehta", "Dr. Rohan Iyer"]
    asha = clinic.doctors[0]
    monday = [(h.start, h.end) for h in asha.hours if h.weekday == 0]
    assert monday == [(time(10), time(13)), (time(17), time(20))]  # split shift
    assert len(clinic.faq) == 2


def test_unknown_clinic_is_not_found(db):
    s, _ = db
    with pytest.raises(repo.NotFound):
        repo.get_clinic(s, 999)


def _asha(s, clinic_id):
    return repo.get_clinic(s, clinic_id).doctors[0]


def test_booking_sets_end_from_slot_length(db):
    s, clinic_id = db
    doctor = _asha(s, clinic_id)
    appt = repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 22, 10, 0), "Ravi", "9876543210")
    assert appt.ends_at == datetime(2026, 9, 22, 10, 15)
    assert appt.status == "booked" and appt.source == "voice"


def test_double_booking_is_refused_by_the_database(db):
    s, clinic_id = db
    doctor = _asha(s, clinic_id)
    slot = datetime(2026, 9, 22, 10, 0)
    repo.book(s, clinic_id, doctor.id, slot, "Ravi", "9876543210")
    with pytest.raises(repo.SlotTaken):
        repo.book(s, clinic_id, doctor.id, slot, "Sunita", "9123456780")
    # the failed attempt left the session usable and nothing half-written
    assert len(repo.appointments_on(s, clinic_id, slot.date())) == 1


def test_cancelled_slot_can_be_rebooked(db):
    s, clinic_id = db
    doctor = _asha(s, clinic_id)
    slot = datetime(2026, 9, 22, 10, 0)
    first = repo.book(s, clinic_id, doctor.id, slot, "Ravi", "9876543210")
    repo.cancel_appointment(s, first.id)
    repo.book(s, clinic_id, doctor.id, slot, "Sunita", "9123456780")
    assert repo.booked_intervals(s, doctor.id, slot.date()) == [(slot, datetime(2026, 9, 22, 10, 15))]


def test_same_phone_is_one_patient_latest_name_wins(db):
    s, clinic_id = db
    doctor = _asha(s, clinic_id)
    a = repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 22, 10, 0), "Ravi", "9876543210")
    b = repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 23, 10, 0), "Ravi Kumar", "9876543210")
    assert a.patient_id == b.patient_id
    assert b.patient.name == "Ravi Kumar"


def test_doctor_from_another_clinic_cannot_be_booked(db):
    s, clinic_id = db
    other = repo.create_clinic(s, name="Other Clinic")
    doctor = _asha(s, clinic_id)
    with pytest.raises(repo.NotFound):
        repo.book(s, other.id, doctor.id, datetime(2026, 9, 22, 10), "Ravi", "9876543210")


def test_booked_intervals_are_per_day(db):
    s, clinic_id = db
    doctor = _asha(s, clinic_id)
    repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 22, 10, 0), "A", "9000000001")
    repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 23, 10, 0), "B", "9000000002")
    assert repo.booked_intervals(s, doctor.id, date(2026, 9, 22)) == [
        (datetime(2026, 9, 22, 10, 0), datetime(2026, 9, 22, 10, 15))
    ]


def test_time_off_overlap_includes_clinic_holidays(db):
    s, clinic_id = db
    doctor = _asha(s, clinic_id)
    repo.add_time_off(s, clinic_id, date(2026, 10, 2), date(2026, 10, 2), reason="Gandhi Jayanti")
    repo.add_time_off(s, clinic_id, date(2026, 10, 5), date(2026, 10, 9), doctor_id=doctor.id)
    hits = repo.time_off_overlapping(s, clinic_id, date(2026, 10, 1), date(2026, 10, 6))
    assert [(t.doctor_id, t.date_from) for t in hits] == [
        (None, date(2026, 10, 2)), (doctor.id, date(2026, 10, 5)),
    ]


def test_invalid_schedule_and_time_off_are_rejected(db):
    s, clinic_id = db
    doctor = _asha(s, clinic_id)
    with pytest.raises(ValueError):
        repo.set_doctor_hours(s, doctor.id, [(0, time(13), time(10))])
    with pytest.raises(ValueError):
        repo.set_doctor_hours(s, doctor.id, [(7, time(10), time(13))])
    with pytest.raises(ValueError):
        repo.add_time_off(s, clinic_id, date(2026, 10, 5), date(2026, 10, 1))


def test_deleting_a_doctor_removes_their_hours(db):
    s, clinic_id = db
    doctor = repo.get_clinic(s, clinic_id).doctors[1]
    repo.delete_doctor(s, doctor.id)
    s.expire_all()
    assert [d.name for d in repo.get_clinic(s, clinic_id).doctors] == ["Dr. Asha Mehta"]
