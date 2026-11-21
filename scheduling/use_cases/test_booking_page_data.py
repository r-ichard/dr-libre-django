"""Read-only loaders of the booking pages."""

from __future__ import annotations

import pytest

from scheduling.models import Appointment, User
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases.test_booking_support import NOW, VISITOR_EMAIL, _at, _held

pytestmark = pytest.mark.django_db


def returns_masked_email_and_attempts_left_when_hold_is_open() -> None:
    from scheduling.use_cases.booking_page_data import hold_summary

    clinic = make_clinic()
    with _at(NOW):
        hold = _held(clinic)
        summary = hold_summary(hold.pk)

    assert summary is not None
    assert summary.masked_email == "v***@example.test"
    assert VISITOR_EMAIL not in repr(summary)
    assert summary.attempts_left == 5


def returns_none_when_hold_is_expired() -> None:
    from datetime import timedelta

    from scheduling.use_cases.booking_page_data import hold_summary

    clinic = make_clinic()
    with _at(NOW):
        hold = _held(clinic)
    with _at(NOW + timedelta(minutes=11)):
        assert hold_summary(hold.pk) is None


def returns_appointment_only_for_its_own_patient() -> None:
    from scheduling.use_cases.booking_page_data import appointment_for_patient

    clinic = make_clinic()
    appointment = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
    )
    stranger = make("User")
    assert isinstance(appointment, Appointment)
    assert isinstance(stranger, User)

    assert appointment_for_patient(appointment.pk, clinic.patient) is not None
    assert appointment_for_patient(appointment.pk, stranger) is None


def returns_none_when_clinician_belongs_to_another_department() -> None:
    from scheduling.use_cases.booking_page_data import slot_choice

    clinic = make_clinic()
    other = make_clinic()

    assert slot_choice(clinic.appointment_type.pk, clinic.clinician.pk) is not None
    assert slot_choice(clinic.appointment_type.pk, other.clinician.pk) is None


def returns_the_hospital_time_zone_when_a_week_is_loaded() -> None:
    from datetime import date

    from scheduling.domain.failure import Failure
    from scheduling.use_cases.booking_page_data import week_of_slots

    clinic = make_clinic()

    with _at(NOW):
        loaded = week_of_slots(clinic.appointment_type.pk, None, date(2030, 1, 9))

    assert not isinstance(loaded, Failure)
    assert loaded.value.time_zone.key == clinic.appointment_type.department.hospital.time_zone
    assert loaded.value.time_zone.key != "UTC"
