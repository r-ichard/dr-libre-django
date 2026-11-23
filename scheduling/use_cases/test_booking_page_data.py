"""Read-only loaders of the booking pages."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.domain.failure import Failure
from scheduling.models import Appointment, User
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases.booking_page_data import week_of_slots
from scheduling.use_cases.test_booking_support import NOW, VISITOR_EMAIL, _at, _held

pytestmark = pytest.mark.django_db

SUNDAY_NOON = datetime(2030, 1, 13, 12, 0, tzinfo=UTC)
CURRENT_WEEK = date(2030, 1, 7)
FIRST_FREE_WEEK = date(2030, 1, 14)
SUNDAY_LATE = datetime(2030, 1, 13, 22, 0, tzinfo=UTC)
MONDAY_MORNING = datetime(2030, 1, 7, 8, 0, tzinfo=UTC)


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

    assert (
        slot_choice(clinic.appointment_type.pk, clinic.clinician.pk, online_only=False) is not None
    )
    assert slot_choice(clinic.appointment_type.pk, other.clinician.pk, online_only=False) is None


def returns_the_hospital_time_zone_when_a_week_is_loaded() -> None:
    from datetime import date

    from scheduling.domain.failure import Failure
    from scheduling.use_cases.booking_page_data import week_of_slots

    clinic = make_clinic()

    with _at(NOW):
        loaded = week_of_slots(
            clinic.appointment_type.pk, None, date(2030, 1, 9), online_only=False
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.time_zone.key == clinic.appointment_type.department.hospital.time_zone
    assert loaded.value.time_zone.key != "UTC"


def returns_week_of_first_free_time_when_current_week_has_none_and_week_is_not_named() -> None:
    clinic = make_clinic()

    with _at(SUNDAY_NOON):
        loaded = week_of_slots(
            clinic.appointment_type.pk, None, None, online_only=False, open_on_first_free=True
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == FIRST_FREE_WEEK


def returns_named_week_when_named_week_has_no_free_time() -> None:
    clinic = make_clinic()

    with _at(SUNDAY_NOON):
        loaded = week_of_slots(
            clinic.appointment_type.pk,
            None,
            CURRENT_WEEK,
            online_only=False,
            open_on_first_free=True,
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == CURRENT_WEEK


def returns_current_week_when_nothing_is_free_within_horizon() -> None:
    clinic = make_clinic(rule_fields={"valid_from": date(2030, 7, 1)})

    with _at(SUNDAY_NOON):
        loaded = week_of_slots(
            clinic.appointment_type.pk, None, None, online_only=False, open_on_first_free=True
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == CURRENT_WEEK


def returns_current_week_when_first_free_time_is_after_horizon_end() -> None:
    # The horizon ends on Saturday 13 April 12:00 UTC; the Monday after it must not be reached.
    clinic = make_clinic(rule_fields={"valid_from": date(2030, 4, 15)})

    with _at(SUNDAY_NOON):
        loaded = week_of_slots(
            clinic.appointment_type.pk, None, None, online_only=False, open_on_first_free=True
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == CURRENT_WEEK


def returns_week_of_slot_that_crosses_the_first_chunk_border() -> None:
    clinic = make_clinic(
        rule_fields={
            "weekday": 3,
            "start_time": time(14, 45),
            "end_time": time(15, 15),
            "valid_from": date(2030, 2, 13),
        }
    )

    with _at(SUNDAY_NOON):
        loaded = week_of_slots(
            clinic.appointment_type.pk, None, None, online_only=False, open_on_first_free=True
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == date(2030, 2, 11)


def returns_current_week_for_visitor_when_only_hidden_clinicians_are_free() -> None:
    clinic = make_clinic()
    clinic.clinician.specialty.is_active = False
    clinic.clinician.specialty.save()

    with _at(SUNDAY_NOON):
        loaded = week_of_slots(
            clinic.appointment_type.pk, None, None, online_only=True, open_on_first_free=True
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == CURRENT_WEEK


def returns_first_free_week_for_staff_when_only_hidden_clinicians_are_free() -> None:
    clinic = make_clinic()
    clinic.clinician.specialty.is_active = False
    clinic.clinician.specialty.save()

    with _at(SUNDAY_NOON):
        loaded = week_of_slots(
            clinic.appointment_type.pk, None, None, online_only=False, open_on_first_free=True
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == FIRST_FREE_WEEK


def returns_at_most_37_queries_when_first_free_time_is_in_last_horizon_chunk() -> None:
    clinic = make_clinic(
        type_fields={"needs_room": True}, rule_fields={"valid_from": date(2030, 3, 18)}
    )
    make("Room", department=clinic.department)

    with _at(SUNDAY_NOON), CaptureQueriesContext(connection) as captured:
        loaded = week_of_slots(
            clinic.appointment_type.pk,
            clinic.clinician.pk,
            None,
            online_only=True,
            open_on_first_free=True,
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == date(2030, 3, 18)
    assert len(captured.captured_queries) <= 37


def returns_current_week_when_first_free_time_is_not_asked_for() -> None:
    clinic = make_clinic()

    with _at(SUNDAY_NOON):
        loaded = week_of_slots(clinic.appointment_type.pk, None, None, online_only=False)

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == CURRENT_WEEK


def returns_week_after_lead_time_when_first_free_time_is_inside_lead_time() -> None:
    clinic = make_clinic(rule_fields={"start_time": time(0, 30), "end_time": time(1, 0)})

    with _at(SUNDAY_LATE):
        loaded = week_of_slots(
            clinic.appointment_type.pk, None, None, online_only=False, open_on_first_free=True
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == date(2030, 1, 21)


def returns_same_query_count_as_plain_week_when_current_week_has_slots() -> None:
    clinic = make_clinic()

    with _at(MONDAY_MORNING), CaptureQueriesContext(connection) as plain:
        week_of_slots(clinic.appointment_type.pk, None, None, online_only=False)
    with _at(MONDAY_MORNING), CaptureQueriesContext(connection) as first_free:
        loaded = week_of_slots(
            clinic.appointment_type.pk, None, None, online_only=False, open_on_first_free=True
        )

    assert not isinstance(loaded, Failure)
    assert loaded.value.week_start == CURRENT_WEEK
    assert len(first_free.captured_queries) == len(plain.captured_queries)
