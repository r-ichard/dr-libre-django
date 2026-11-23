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
from scheduling.models import Room
from scheduling.models.builders import STARTS_AT, Clinic, add_clinician, make, make_clinic
from scheduling.use_cases.free_slots_query import find_free_slots
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.test_booking_support import (
    _create,
    _held,
    _last_code,
    _verify,
)

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
MONDAY = TimeRange(datetime(2030, 1, 7, 0, 0, tzinfo=UTC), datetime(2030, 1, 8, 0, 0, tzinfo=UTC))
# 08:00 to 10:00 Berlin is 07:00 to 09:00 UTC: the 07:00 and 07:30 starts fall inside
# the 120 minute lead time from 06:00 UTC; 08:00 is exactly at its edge and stays offered.
LEAD_TIME_RULE = {"start_time": time(8, 0), "end_time": time(10, 0), "slot_step_minutes": 30}
HOUR_OF_SLOTS = {"start_time": time(11, 0), "end_time": time(12, 0), "slot_step_minutes": 30}
# 09:00 Berlin is 08:00 UTC; one 30 minute start, shared by both cardiologists.
NINE_OCLOCK_RULE = {"start_time": time(9, 0), "end_time": time(9, 30), "slot_step_minutes": 30}
NINE_OCLOCK = datetime(2030, 1, 7, 8, 0, tzinfo=UTC)
SECOND_VISITOR_EMAIL = "second.visitor@example.test"


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-slots", NOW)):
        yield


def _starts(offers: Sequence[SlotOffer]) -> list[datetime]:
    return [offer.start for offer in offers]


def _cardiology_with_one_room(extra_room_code: str | None = None) -> Clinic:
    """Two cardiologists sharing one room, Heart, and a room-needing 30 minute type."""
    clinic = make_clinic(type_fields={"needs_room": True}, rule_fields=NINE_OCLOCK_RULE)
    add_clinician(clinic.department, NINE_OCLOCK_RULE)
    make("Room", department=clinic.department, code="heart")
    if extra_room_code is not None:
        make("Room", department=clinic.department, code=extra_room_code)
    return clinic


def _first_visitor_books_nine_oclock(clinic: Clinic) -> None:
    hold = _held(clinic, clinician_id=None, starts_at=NINE_OCLOCK)
    assert isinstance(_verify(hold.pk, _last_code()), Success)


def _booking_in_heart(
    clinic: Clinic, starts_at: datetime, status: str = "BOOKED", cancellation_reason: str = ""
) -> None:
    make(
        "Appointment",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        room=Room.objects.get(department=clinic.department, code="heart"),
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        status=status,
        cancellation_reason=cancellation_reason,
        cancelled_at=NINE_OCLOCK if cancellation_reason else None,
    )


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


def returns_no_start_60_minutes_away_when_caller_is_online_only() -> None:
    clinic = make_clinic(rule_fields=LEAD_TIME_RULE)

    result = find_free_slots(
        clinic.appointment_type.pk, clinic.clinician.pk, MONDAY, online_only=True
    )

    assert isinstance(result, Success)
    assert _starts(result.value.offers) == [
        datetime(2030, 1, 7, 8, 0, tzinfo=UTC),
        datetime(2030, 1, 7, 8, 30, tzinfo=UTC),
    ]


def returns_start_60_minutes_away_when_caller_is_staff() -> None:
    clinic = make_clinic(rule_fields=LEAD_TIME_RULE)

    result = find_free_slots(
        clinic.appointment_type.pk, clinic.clinician.pk, MONDAY, online_only=False
    )

    assert isinstance(result, Success)
    assert _starts(result.value.offers) == [
        datetime(2030, 1, 7, 7, 0, tzinfo=UTC),
        datetime(2030, 1, 7, 7, 30, tzinfo=UTC),
        datetime(2030, 1, 7, 8, 0, tzinfo=UTC),
        datetime(2030, 1, 7, 8, 30, tzinfo=UTC),
    ]


def returns_no_offer_and_no_room_when_first_booking_takes_the_only_room() -> None:
    clinic = _cardiology_with_one_room()
    _first_visitor_books_nine_oclock(clinic)

    offered = find_free_slots(clinic.appointment_type.pk, None, MONDAY, online_only=False)
    second = _create(clinic, clinician_id=None, starts_at=NINE_OCLOCK, email=SECOND_VISITOR_EMAIL)

    assert isinstance(offered, Success)
    assert NINE_OCLOCK not in _starts(offered.value.offers)
    assert second == Failure.no_room_available()


def returns_no_offer_at_nine_when_the_only_room_has_a_later_booking_too() -> None:
    clinic = _cardiology_with_one_room()
    _first_visitor_books_nine_oclock(clinic)
    _booking_in_heart(clinic, datetime(2030, 1, 7, 13, 0, tzinfo=UTC))

    offered = find_free_slots(clinic.appointment_type.pk, None, MONDAY, online_only=False)

    assert isinstance(offered, Success)
    assert NINE_OCLOCK not in _starts(offered.value.offers)


def returns_nine_oclock_offer_when_the_only_room_booking_is_cancelled() -> None:
    clinic = _cardiology_with_one_room()
    _booking_in_heart(clinic, NINE_OCLOCK, "CANCELLED", "Cannot come")

    offered = find_free_slots(clinic.appointment_type.pk, None, MONDAY, online_only=False)

    assert isinstance(offered, Success)
    assert NINE_OCLOCK in _starts(offered.value.offers)


def returns_nine_oclock_offer_and_second_hold_when_second_room_is_free() -> None:
    clinic = _cardiology_with_one_room(extra_room_code="lab")
    _first_visitor_books_nine_oclock(clinic)

    offered = find_free_slots(clinic.appointment_type.pk, None, MONDAY, online_only=False)
    second = _create(clinic, clinician_id=None, starts_at=NINE_OCLOCK, email=SECOND_VISITOR_EMAIL)

    assert isinstance(offered, Success)
    assert NINE_OCLOCK in _starts(offered.value.offers)
    assert isinstance(second, Success)
