"""Section 5.3: every violated booking rule by name, for who acts and what they do."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from scheduling.domain.appointment_status import is_active
from scheduling.models.booking import AppointmentSource, AppointmentStatus
from scheduling.models.people import Role

LEAD_TIME = timedelta(minutes=120)
CANCELLATION_WINDOW = timedelta(hours=24)
OPEN_ONLINE_BOOKINGS_MAXIMUM = 3


class BookingAction(StrEnum):
    BOOK = "book"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"


class BookingRule(StrEnum):
    LEAD_TIME_TOO_SHORT = "lead_time_too_short"
    CANCELLATION_WINDOW_CLOSED = "cancellation_window_closed"
    TOO_MANY_OPEN_BOOKINGS = "too_many_open_bookings"
    TYPE_NOT_BOOKABLE_ONLINE = "type_not_bookable_online"
    OUTSIDE_AVAILABILITY = "outside_availability"


@dataclass(frozen=True)
class BookingAttempt:
    action: BookingAction
    actor_role: Role
    now: datetime
    new_start: datetime | None
    current_start: datetime | None
    open_online_bookings: int
    type_bookable_online: bool
    slot_is_free: bool


@dataclass(frozen=True)
class BookingSummary:
    starts_at: datetime
    status: AppointmentStatus
    source: AppointmentSource


def violated_rules(attempt: BookingAttempt) -> list[BookingRule]:
    action = attempt.action
    if action != BookingAction.CANCEL and attempt.new_start is None:
        raise ValueError("new_start is required to book or reschedule")
    if action != BookingAction.BOOK and attempt.current_start is None:
        raise ValueError("current_start is required to reschedule or cancel")
    patient_rules = attempt.actor_role == Role.PATIENT
    booking = action == BookingAction.BOOK
    cancelling = action == BookingAction.CANCEL
    violations = [
        (patient_rules and not cancelling and _too_soon(attempt), BookingRule.LEAD_TIME_TOO_SHORT),
        (
            patient_rules and not booking and _window_closed(attempt),
            BookingRule.CANCELLATION_WINDOW_CLOSED,
        ),
        (
            patient_rules
            and booking
            and attempt.open_online_bookings >= OPEN_ONLINE_BOOKINGS_MAXIMUM,
            BookingRule.TOO_MANY_OPEN_BOOKINGS,
        ),
        (
            patient_rules and not cancelling and not attempt.type_bookable_online,
            BookingRule.TYPE_NOT_BOOKABLE_ONLINE,
        ),
        (not cancelling and not attempt.slot_is_free, BookingRule.OUTSIDE_AVAILABILITY),
    ]
    return [rule for violated, rule in violations if violated]


def count_open_online_bookings(appointments: Sequence[BookingSummary], now: datetime) -> int:
    return sum(
        1
        for appointment in appointments
        if appointment.starts_at > now
        and is_active(appointment.status)
        and appointment.source != AppointmentSource.STAFF
    )


def _too_soon(attempt: BookingAttempt) -> bool:
    return attempt.new_start is not None and attempt.new_start - attempt.now < LEAD_TIME


def _window_closed(attempt: BookingAttempt) -> bool:
    return (
        attempt.current_start is not None
        and attempt.current_start - attempt.now < CANCELLATION_WINDOW
    )
