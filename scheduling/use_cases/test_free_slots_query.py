"""Section 5.1 and 7.1: the free slots a visitor sees, holds counted, constant query count."""

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, time, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.domain.failure import Failure, FieldMessage, Success
from scheduling.domain.free_slots import TimeRange
from scheduling.domain.request_context import RequestContext
from scheduling.domain.slot_search import SlotOffer
from scheduling.models.builders import STARTS_AT, add_clinician, make, make_clinic
from scheduling.use_cases.free_slots_query import find_free_slots
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
MONDAY = TimeRange(datetime(2030, 1, 7, 0, 0, tzinfo=UTC), datetime(2030, 1, 8, 0, 0, tzinfo=UTC))
HOUR_OF_SLOTS = {"start_time": time(11, 0), "end_time": time(12, 0), "slot_step_minutes": 30}


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-slots", NOW)):
        yield


def _starts(offers: Sequence[SlotOffer]) -> list[datetime]:
    return [offer.start for offer in offers]


def returns_union_one_entry_per_start_when_no_clinician_named() -> None:
    first = make_clinic(
        rule_fields={"start_time": time(9, 0), "end_time": time(10, 0), "slot_step_minutes": 30}
    )
    second = add_clinician(
        first.department,
        {"start_time": time(9, 30), "end_time": time(10, 30), "slot_step_minutes": 30},
    )

    result = find_free_slots(first.appointment_type.pk, None, MONDAY, online_only=False)

    assert isinstance(result, Success)
    offered = {offer.start: set(offer.clinician_ids) for offer in result.value.offers}
    both = {first.clinician.pk, second.pk}
    assert offered == {
        datetime(2030, 1, 7, 8, 0, tzinfo=UTC): {first.clinician.pk},
        datetime(2030, 1, 7, 8, 30, tzinfo=UTC): both,
        datetime(2030, 1, 7, 9, 0, tzinfo=UTC): {second.pk},
    }


def returns_hospital_time_zone_beside_the_offers() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)

    result = find_free_slots(
        clinic.appointment_type.pk, clinic.clinician.pk, MONDAY, online_only=False
    )

    assert isinstance(result, Success)
    assert result.value.time_zone == "Europe/Berlin"


def returns_only_the_named_clinician_when_one_is_named() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    add_clinician(clinic.department, HOUR_OF_SLOTS)

    result = find_free_slots(
        clinic.appointment_type.pk, clinic.clinician.pk, MONDAY, online_only=False
    )

    assert isinstance(result, Success)
    assert {identifier for offer in result.value.offers for identifier in offer.clinician_ids} == {
        clinic.clinician.pk
    }


def returns_no_slot_when_unexpired_hold_covers_it() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    make(
        "BookingHold",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=datetime(2030, 1, 7, 10, 0, tzinfo=UTC),
        ends_at=datetime(2030, 1, 7, 10, 30, tzinfo=UTC),
        expires_at=NOW + timedelta(minutes=10),
    )

    result = find_free_slots(
        clinic.appointment_type.pk, clinic.clinician.pk, MONDAY, online_only=False
    )

    assert isinstance(result, Success)
    assert _starts(result.value.offers) == [datetime(2030, 1, 7, 10, 30, tzinfo=UTC)]


def returns_slot_when_hold_expired() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    make(
        "BookingHold",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=datetime(2030, 1, 7, 10, 0, tzinfo=UTC),
        ends_at=datetime(2030, 1, 7, 10, 30, tzinfo=UTC),
        expires_at=NOW - timedelta(minutes=1),
    )

    result = find_free_slots(
        clinic.appointment_type.pk, clinic.clinician.pk, MONDAY, online_only=False
    )

    assert isinstance(result, Success)
    assert _starts(result.value.offers)[0] == datetime(2030, 1, 7, 10, 0, tzinfo=UTC)


def returns_no_slot_when_active_appointment_covers_it() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    make(
        "Appointment",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=STARTS_AT,
        ends_at=STARTS_AT + timedelta(minutes=30),
    )

    result = find_free_slots(
        clinic.appointment_type.pk, clinic.clinician.pk, MONDAY, online_only=False
    )

    assert isinstance(result, Success)
    assert _starts(result.value.offers) == [datetime(2030, 1, 7, 10, 30, tzinfo=UTC)]


def returns_not_found_when_type_inactive() -> None:
    clinic = make_clinic(type_fields={"is_active": False})

    result = find_free_slots(clinic.appointment_type.pk, None, MONDAY, online_only=False)

    assert result == Failure.not_found()


def returns_not_found_when_clinician_in_other_department() -> None:
    clinic = make_clinic()
    stranger = add_clinician(make("Department"))

    result = find_free_slots(clinic.appointment_type.pk, stranger.pk, MONDAY, online_only=False)

    assert result == Failure.not_found()


def returns_not_found_when_clinician_user_inactive() -> None:
    clinic = make_clinic()
    gone = add_clinician(clinic.department, user=make("User", role="CLINICIAN", is_active=False))

    result = find_free_slots(clinic.appointment_type.pk, gone.pk, MONDAY, online_only=False)

    assert result == Failure.not_found()


def returns_invalid_input_when_range_over_31_days() -> None:
    clinic = make_clinic()
    too_wide = TimeRange(MONDAY.starts_at, MONDAY.starts_at + timedelta(days=32))

    result = find_free_slots(clinic.appointment_type.pk, None, too_wide, online_only=False)

    assert result == Failure.invalid_input([FieldMessage("to", "The range is at most 31 days.")])


def returns_same_query_count_when_ten_clinicians() -> None:
    few = make_clinic(rule_fields=HOUR_OF_SLOTS)
    add_clinician(few.department, HOUR_OF_SLOTS)
    many = make_clinic(rule_fields=HOUR_OF_SLOTS)
    for _ in range(9):
        add_clinician(many.department, HOUR_OF_SLOTS)

    with CaptureQueriesContext(connection) as for_two:
        find_free_slots(few.appointment_type.pk, None, MONDAY, online_only=False)
    with CaptureQueriesContext(connection) as for_ten:
        find_free_slots(many.appointment_type.pk, None, MONDAY, online_only=False)

    assert len(for_ten) == len(for_two)
