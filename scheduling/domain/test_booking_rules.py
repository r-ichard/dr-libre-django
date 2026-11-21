"""Section 5.3: every violated booking rule by name, for who acts and what they do."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from scheduling.domain.booking_rules import (
    CANCELLATION_WINDOW,
    LEAD_TIME,
    OPEN_ONLINE_BOOKINGS_MAXIMUM,
    BookingAction,
    BookingAttempt,
    BookingRule,
    BookingSummary,
    count_open_online_bookings,
    violated_rules,
)
from scheduling.models.booking import AppointmentSource, AppointmentStatus
from scheduling.models.people import Role

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
FAR = NOW + timedelta(days=5)

BOOK = BookingAttempt(
    action=BookingAction.BOOK,
    actor_role=Role.PATIENT,
    now=NOW,
    new_start=FAR,
    current_start=None,
    open_online_bookings=0,
    type_bookable_online=True,
    slot_is_free=True,
)
RESCHEDULE = replace(BOOK, action=BookingAction.RESCHEDULE, current_start=FAR)
CANCEL = replace(BOOK, action=BookingAction.CANCEL, new_start=None, current_start=FAR)


def returns_the_policy_numbers_when_read_from_one_place() -> None:
    assert timedelta(minutes=120) == LEAD_TIME
    assert timedelta(hours=24) == CANCELLATION_WINDOW
    assert OPEN_ONLINE_BOOKINGS_MAXIMUM == 3


def returns_no_rules_when_patient_books_a_good_slot() -> None:
    assert violated_rules(BOOK) == []


def returns_no_rules_when_start_is_exactly_the_lead_time_away() -> None:
    assert violated_rules(replace(BOOK, new_start=NOW + timedelta(minutes=120))) == []


def returns_lead_time_too_short_when_start_is_119_minutes_away() -> None:
    attempt = replace(BOOK, new_start=NOW + timedelta(minutes=119))
    assert violated_rules(attempt) == [BookingRule.LEAD_TIME_TOO_SHORT]


def returns_no_rules_when_two_bookings_are_open() -> None:
    assert violated_rules(replace(BOOK, open_online_bookings=2)) == []


def returns_too_many_open_bookings_when_three_are_open() -> None:
    assert violated_rules(replace(BOOK, open_online_bookings=3)) == [
        BookingRule.TOO_MANY_OPEN_BOOKINGS
    ]


def returns_type_not_bookable_online_when_type_is_staff_only() -> None:
    assert violated_rules(replace(BOOK, type_bookable_online=False)) == [
        BookingRule.TYPE_NOT_BOOKABLE_ONLINE
    ]


def returns_outside_availability_when_slot_is_not_free() -> None:
    assert violated_rules(replace(BOOK, slot_is_free=False)) == [BookingRule.OUTSIDE_AVAILABILITY]


def returns_every_violated_rule_when_several_fail_at_once() -> None:
    attempt = replace(
        BOOK,
        new_start=NOW + timedelta(minutes=30),
        open_online_bookings=3,
        type_bookable_online=False,
        slot_is_free=False,
    )
    assert violated_rules(attempt) == [
        BookingRule.LEAD_TIME_TOO_SHORT,
        BookingRule.TOO_MANY_OPEN_BOOKINGS,
        BookingRule.TYPE_NOT_BOOKABLE_ONLINE,
        BookingRule.OUTSIDE_AVAILABILITY,
    ]


@pytest.mark.parametrize("role", [Role.CLINICIAN, Role.ADMIN])
def returns_only_outside_availability_when_staff_books_a_slot_that_is_not_free(
    role: Role,
) -> None:
    attempt = replace(
        BOOK,
        actor_role=role,
        new_start=NOW + timedelta(minutes=1),
        open_online_bookings=9,
        type_bookable_online=False,
        slot_is_free=False,
    )
    assert violated_rules(attempt) == [BookingRule.OUTSIDE_AVAILABILITY]


def returns_no_rules_when_patient_cancels_25_hours_ahead() -> None:
    attempt = replace(CANCEL, current_start=NOW + timedelta(hours=25), slot_is_free=False)
    assert violated_rules(attempt) == []


def returns_no_rules_when_patient_cancels_exactly_24_hours_ahead() -> None:
    assert violated_rules(replace(CANCEL, current_start=NOW + timedelta(hours=24))) == []


def returns_cancellation_window_closed_when_patient_cancels_23_hours_59_ahead() -> None:
    attempt = replace(CANCEL, current_start=NOW + timedelta(hours=23, minutes=59))
    assert violated_rules(attempt) == [BookingRule.CANCELLATION_WINDOW_CLOSED]


@pytest.mark.parametrize("role", [Role.CLINICIAN, Role.ADMIN])
def returns_no_rules_when_staff_cancels_an_appointment_that_starts_soon(role: Role) -> None:
    attempt = replace(CANCEL, actor_role=role, current_start=NOW + timedelta(minutes=5))
    assert violated_rules(attempt) == []


def returns_no_rules_when_patient_reschedules_with_good_starts() -> None:
    assert violated_rules(RESCHEDULE) == []


def returns_cancellation_window_closed_when_reschedule_current_start_is_under_24_hours() -> None:
    attempt = replace(RESCHEDULE, current_start=NOW + timedelta(hours=3))
    assert violated_rules(attempt) == [BookingRule.CANCELLATION_WINDOW_CLOSED]


def returns_no_cancellation_rule_when_reschedule_current_start_is_24_hours_away_but_new_start_is_close() -> (  # noqa: E501
    None
):
    attempt = replace(
        RESCHEDULE,
        current_start=NOW + timedelta(hours=25),
        new_start=NOW + timedelta(minutes=60),
    )
    assert violated_rules(attempt) == [BookingRule.LEAD_TIME_TOO_SHORT]


def returns_lead_time_too_short_from_new_start_not_current_start_when_rescheduling() -> None:
    attempt = replace(
        RESCHEDULE,
        current_start=NOW + timedelta(hours=3),
        new_start=NOW + timedelta(minutes=30),
    )
    assert violated_rules(attempt) == [
        BookingRule.LEAD_TIME_TOO_SHORT,
        BookingRule.CANCELLATION_WINDOW_CLOSED,
    ]


def returns_no_open_booking_rule_when_patient_reschedules_with_three_open() -> None:
    assert violated_rules(replace(RESCHEDULE, open_online_bookings=3)) == []


def returns_type_and_availability_rules_when_patient_reschedules_badly() -> None:
    attempt = replace(RESCHEDULE, type_bookable_online=False, slot_is_free=False)
    assert violated_rules(attempt) == [
        BookingRule.TYPE_NOT_BOOKABLE_ONLINE,
        BookingRule.OUTSIDE_AVAILABILITY,
    ]


def returns_only_outside_availability_when_staff_reschedules_to_a_taken_slot() -> None:
    attempt = replace(
        RESCHEDULE,
        actor_role=Role.ADMIN,
        current_start=NOW + timedelta(minutes=5),
        new_start=NOW + timedelta(minutes=5),
        slot_is_free=False,
    )
    assert violated_rules(attempt) == [BookingRule.OUTSIDE_AVAILABILITY]


def raises_when_reschedule_has_no_current_start() -> None:
    with pytest.raises(ValueError, match="current_start"):
        violated_rules(replace(RESCHEDULE, current_start=None))


def raises_when_book_has_no_new_start() -> None:
    with pytest.raises(ValueError, match="new_start"):
        violated_rules(replace(BOOK, new_start=None))


def raises_when_cancel_has_no_current_start() -> None:
    with pytest.raises(ValueError, match="current_start"):
        violated_rules(replace(CANCEL, current_start=None))


def _summary(
    status: AppointmentStatus = AppointmentStatus.BOOKED,
    source: AppointmentSource = AppointmentSource.ONLINE,
    starts_at: datetime = FAR,
) -> BookingSummary:
    return BookingSummary(starts_at=starts_at, status=status, source=source)


def returns_count_of_future_active_online_and_round_robin_bookings() -> None:
    appointments = [
        _summary(),
        _summary(source=AppointmentSource.ROUND_ROBIN, status=AppointmentStatus.CONFIRMED),
        _summary(source=AppointmentSource.STAFF),
        _summary(starts_at=NOW - timedelta(minutes=1)),
        _summary(status=AppointmentStatus.CANCELLED),
        _summary(status=AppointmentStatus.NO_SHOW),
    ]
    assert count_open_online_bookings(appointments, NOW) == 2


def returns_no_rules_when_patient_books_and_an_unused_current_start_is_soon() -> None:
    attempt = replace(BOOK, current_start=NOW + timedelta(minutes=1))
    assert violated_rules(attempt) == []


def returns_only_window_rule_when_patient_cancels_and_an_unused_new_start_is_soon() -> None:
    attempt = replace(
        CANCEL, new_start=NOW + timedelta(minutes=1), current_start=NOW + timedelta(hours=1)
    )
    assert violated_rules(attempt) == [BookingRule.CANCELLATION_WINDOW_CLOSED]


def returns_count_without_booking_that_starts_exactly_now() -> None:
    assert count_open_online_bookings([_summary(starts_at=NOW)], NOW) == 0
