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


def test_family_sharing_a_phone_are_separate_patients(db):
    # The reported bug: booking for Yash on Harsh's number renamed Harsh.
    s, clinic_id = db
    doctor = _asha(s, clinic_id)
    harsh = repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 22, 10, 0), "Harsh", "8928803112")
    yash = repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 22, 10, 15), "Yash", "8928803112")
    s.expire_all()
    assert harsh.patient_id != yash.patient_id
    assert repo.get_appointment(s, harsh.id).patient.name == "Harsh"
    assert repo.get_appointment(s, yash.id).patient.name == "Yash"


def test_same_name_in_other_case_is_the_same_patient_and_keeps_its_spelling(db):
    s, clinic_id = db
    doctor = _asha(s, clinic_id)
    a = repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 22, 10, 0), "Harsh", "8928803112")
    b = repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 23, 10, 0), " harsh ", "8928803112")
    assert a.patient_id == b.patient_id
    assert b.patient.name == "Harsh"


def test_other_constraint_errors_are_not_reported_as_slot_taken(db):
    # A 'slot taken' reply for a different failure would send callers chasing
    # other times; anything but the slot index must surface as itself.
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    s, clinic_id = db
    s.execute(text("CREATE UNIQUE INDEX one_patient_per_phone ON patients (clinic_id, phone)"))
    s.commit()
    doctor = _asha(s, clinic_id)
    repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 22, 10, 0), "Harsh", "8928803112")
    with pytest.raises(IntegrityError):
        repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 22, 10, 15), "Yash", "8928803112")


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


def test_deleting_a_doctor_removes_them_with_hours_leave_and_history(db):
    s, clinic_id = db
    doctor = repo.get_clinic(s, clinic_id).doctors[1]
    past = repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 14, 11, 0), "Ravi", "9876543210").id
    repo.add_time_off(s, clinic_id, date(2026, 10, 5), date(2026, 10, 6), doctor_id=doctor.id)
    repo.delete_doctor(s, doctor.id, now=datetime(2026, 9, 21, 9, 0))
    s.expire_all()
    assert [d.name for d in repo.get_clinic(s, clinic_id).doctors] == ["Dr. Asha Mehta"]
    assert repo.time_off_overlapping(s, clinic_id, date(2026, 10, 1), date(2026, 10, 31)) == []
    with pytest.raises(repo.NotFound):
        repo.get_appointment(s, past)


def test_a_doctor_with_upcoming_bookings_cant_be_deleted(db):
    s, clinic_id = db
    doctor = repo.get_clinic(s, clinic_id).doctors[1]
    appt = repo.book(s, clinic_id, doctor.id, datetime(2026, 9, 23, 11, 0), "Ravi", "9876543210")
    now = datetime(2026, 9, 21, 9, 0)
    with pytest.raises(ValueError, match="Dr. Rohan Iyer has 1 upcoming appointment. Cancel them"):
        repo.delete_doctor(s, doctor.id, now)
    assert repo.upcoming_counts(s, clinic_id, now) == {doctor.id: 1}
    repo.cancel_appointment(s, appt.id)
    repo.delete_doctor(s, doctor.id, now)
    assert repo.upcoming_counts(s, clinic_id, now) == {}


# ---------- call-link slugs ----------

@pytest.mark.parametrize(("name", "slug"), [
    ("Sharma Skin Clinic", "sharma-skin-clinic"),
    ("  Dr. Mehta's  Clinic & Lab ", "dr-mehta-s-clinic-lab"),
    ("Café Dental", "cafe-dental"),
    ("शर्मा क्लिनिक", "clinic"),  # no Latin letters: a placeholder the clinic renames
])
def test_slugify(name, slug):
    assert repo.slugify(name) == slug


def test_new_clinics_get_a_free_slug_and_can_be_found_by_it(db):
    s, clinic_id = db
    first = repo.create_clinic(s, name="Sharma Skin Clinic")
    second = repo.create_clinic(s, name="Sharma Skin Clinic")
    assert (first.slug, second.slug) == ("sharma-skin-clinic", "sharma-skin-clinic-2")
    assert repo.get_clinic_by_slug(s, "sharma-skin-clinic-2").id == second.id
    with pytest.raises(repo.NotFound):
        repo.get_clinic_by_slug(s, "no-such-clinic")


@pytest.mark.parametrize("bad", ["ab", "Sharma", "sharma skin", "sharma--skin", "-sharma", "x" * 61])
def test_invalid_slugs_are_refused(db, bad):
    s, clinic_id = db
    with pytest.raises(ValueError, match="3-60 characters"):
        repo.set_slug(s, clinic_id, bad)


def test_a_taken_slug_is_refused(db):
    s, clinic_id = db
    other = repo.create_clinic(s, name="Other Clinic")
    with pytest.raises(ValueError, match="already taken"):
        repo.set_slug(s, other.id, repo.get_clinic(s, clinic_id).slug)


def test_slug_changes_only_through_set_slug(db):
    s, clinic_id = db
    with pytest.raises(TypeError):
        repo.update_clinic(s, clinic_id, slug="sneaky")


# ---------- dashboard access ----------

def test_members_are_per_clinic_and_emails_are_normalised(db):
    s, clinic_id = db
    other = repo.create_clinic(s, name="Other Clinic")
    repo.add_member(s, clinic_id, "  Reception@Example.COM ")
    repo.add_member(s, clinic_id, "reception@example.com")  # twice: no-op
    repo.add_member(s, other.id, "reception@example.com")
    assert [m.email for m in repo.list_members(s, clinic_id)] == ["reception@example.com"]
    assert repo.clinic_ids_for_email(s, "RECEPTION@example.com") == {clinic_id, other.id}
    assert repo.clinic_ids_for_email(s, "stranger@example.com") == set()


@pytest.mark.parametrize("bad", ["", "not-an-email", "a@b", "two words@example.com"])
def test_bad_emails_are_refused(db, bad):
    s, clinic_id = db
    with pytest.raises(ValueError, match="doesn't look like an email"):
        repo.add_member(s, clinic_id, bad)


def test_removing_a_member_revokes_access(db):
    s, clinic_id = db
    member = repo.add_member(s, clinic_id, "reception@example.com")
    repo.remove_member(s, member.id)
    assert repo.clinic_ids_for_email(s, "reception@example.com") == set()


def test_overlapping_sittings_on_a_day_are_refused(db):
    s, clinic_id = db
    doctor = repo.get_clinic(s, clinic_id).doctors[0]
    with pytest.raises(ValueError, match="sittings on Tuesday overlap"):
        repo.set_doctor_hours(s, doctor.id, [(1, time(10), time(13)), (1, time(12), time(15))])
    # back to back is fine, and the same times on different days are too
    repo.set_doctor_hours(s, doctor.id, [(1, time(10), time(13)), (1, time(13), time(15)), (2, time(12), time(15))])


def test_rows_are_only_found_in_their_own_clinic(db):
    s, clinic_id = db
    other = repo.create_clinic(s, name="Other Clinic")
    faq = repo.get_clinic(s, clinic_id).faq[0]
    assert repo.in_clinic(s, repo.ClinicFaq, faq.id, clinic_id) is faq
    with pytest.raises(repo.NotFound):
        repo.in_clinic(s, repo.ClinicFaq, faq.id, other.id)
    with pytest.raises(repo.NotFound):
        repo.in_clinic(s, repo.ClinicFaq, 99999, clinic_id)
