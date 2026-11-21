"""Section 5.1 and 7.1: what blocks a slot (buffer, hold, time off) and where the range ends."""

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta

import pytest

from scheduling.domain.failure import Failure, FieldMessage, Success
from scheduling.domain.free_slots import TimeRange
from scheduling.domain.request_context import RequestContext
from scheduling.models.builders import STARTS_AT, Clinic, make, make_clinic
from scheduling.use_cases.free_slots_query import find_free_slots
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
FIFTEEN_MINUTES = timedelta(minutes=15)
THIRTY_MINUTES = timedelta(minutes=30)
FROM_FIRST_SLOT = TimeRange(STARTS_AT, STARTS_AT + timedelta(hours=1))


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-loading", NOW)):
        yield


def _hour_of_slots() -> dict[str, object]:
    return {"start_time": time(11, 0), "end_time": time(12, 0), "slot_step_minutes": 30}


def _buffered_clinic() -> Clinic:
    return make_clinic(type_fields={"buffer_minutes": 15}, rule_fields=_hour_of_slots())


def _offered(clinic: Clinic, window: TimeRange = FROM_FIRST_SLOT) -> list[datetime]:
    result = find_free_slots(clinic.appointment_type.pk, clinic.clinician.pk, window)
    assert isinstance(result, Success)
    return [offer.start for offer in result.value.offers]


def returns_no_first_slot_when_appointment_ended_within_the_buffer_before_range() -> None:
    clinic = _buffered_clinic()
    ended_at = STARTS_AT - timedelta(minutes=5)
    make(
        "Appointment",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=ended_at - THIRTY_MINUTES,
        ends_at=ended_at,
    )

    assert STARTS_AT not in _offered(clinic)


def returns_no_first_slot_when_hold_ended_within_the_buffer_before_range() -> None:
    clinic = _buffered_clinic()
    ended_at = STARTS_AT - timedelta(minutes=5)
    make(
        "BookingHold",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=ended_at - THIRTY_MINUTES,
        ends_at=ended_at,
        expires_at=NOW + timedelta(minutes=10),
    )

    assert STARTS_AT not in _offered(clinic)


def returns_first_slot_when_appointment_ended_before_the_buffer_reaches_it() -> None:
    clinic = _buffered_clinic()
    ended_at = STARTS_AT - FIFTEEN_MINUTES
    make(
        "Appointment",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=ended_at - THIRTY_MINUTES,
        ends_at=ended_at,
    )

    assert STARTS_AT in _offered(clinic)


def returns_no_slot_when_time_off_covers_it() -> None:
    clinic = make_clinic(rule_fields=_hour_of_slots())
    make(
        "TimeOff",
        clinician=clinic.clinician,
        starts_at=STARTS_AT,
        ends_at=STARTS_AT + THIRTY_MINUTES,
    )

    assert STARTS_AT not in _offered(clinic)


def returns_slot_when_the_covering_appointment_is_cancelled() -> None:
    clinic = make_clinic(rule_fields=_hour_of_slots())
    make(
        "Appointment",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=STARTS_AT,
        ends_at=STARTS_AT + THIRTY_MINUTES,
        status="CANCELLED",
        cancelled_at=NOW,
        cancellation_reason="Patient asked",
    )

    assert STARTS_AT in _offered(clinic)


def returns_invalid_input_when_range_is_31_days_and_one_second() -> None:
    clinic = make_clinic()
    window = TimeRange(NOW, NOW + timedelta(days=31, seconds=1))

    result = find_free_slots(clinic.appointment_type.pk, None, window)

    assert result == Failure.invalid_input([FieldMessage("to", "The range is at most 31 days.")])


def returns_success_when_range_is_exactly_31_days() -> None:
    clinic = make_clinic()

    result = find_free_slots(
        clinic.appointment_type.pk, None, TimeRange(NOW, NOW + timedelta(days=31))
    )

    assert isinstance(result, Success)
