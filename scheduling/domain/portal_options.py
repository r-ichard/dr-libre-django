"""What a patient may do with an appointment, and the plain words when not."""

from dataclasses import dataclass
from datetime import datetime

from scheduling.domain.appointment_status import RESCHEDULABLE_STATUSES
from scheduling.domain.booking_rules import CANCELLATION_WINDOW
from scheduling.domain.vocabulary import AppointmentStatus

UPCOMING_STATUSES: frozenset[AppointmentStatus] = frozenset(
    {AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED, AppointmentStatus.CHECKED_IN}
)
FINISHED_REASONS: dict[AppointmentStatus, str] = {
    AppointmentStatus.CANCELLED: "This appointment is already cancelled.",
    AppointmentStatus.COMPLETED: "This appointment already took place.",
    AppointmentStatus.NO_SHOW: "This appointment already took place.",
}
STARTED_REASON = "This appointment has already started."
WINDOW_REASON = "This appointment starts in less than 24 hours."
CHECKED_IN_REASON = "You are already checked in, so the time can no longer be changed."
TYPE_NOT_ONLINE_REASON = "This appointment type cannot be booked online."


@dataclass(frozen=True)
class ChangeOption:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class AppointmentOptions:
    cancel: ChangeOption
    reschedule: ChangeOption


def is_upcoming(status: AppointmentStatus, starts_at: datetime, now: datetime) -> bool:
    return status in UPCOMING_STATUSES and starts_at > now


def appointment_options(
    status: AppointmentStatus,
    starts_at: datetime,
    now: datetime,
    type_bookable_online: bool = True,
) -> AppointmentOptions:
    blocked = _blocked_reason(status, starts_at, now)
    if blocked:
        return AppointmentOptions(ChangeOption(False, blocked), ChangeOption(False, blocked))
    return AppointmentOptions(
        ChangeOption(True, ""),
        _reschedule_option(status, type_bookable_online),
    )


def _reschedule_option(status: AppointmentStatus, type_bookable_online: bool) -> ChangeOption:
    if not type_bookable_online:
        return ChangeOption(False, TYPE_NOT_ONLINE_REASON)
    if status not in RESCHEDULABLE_STATUSES:
        return ChangeOption(False, CHECKED_IN_REASON)
    return ChangeOption(True, "")


def _blocked_reason(status: AppointmentStatus, starts_at: datetime, now: datetime) -> str:
    if status in FINISHED_REASONS:
        return FINISHED_REASONS[status]
    if starts_at <= now:
        return STARTED_REASON
    if starts_at - now < CANCELLATION_WINDOW:
        return WINDOW_REASON
    return ""


def expects_change_hint(status: AppointmentStatus) -> bool:
    """Only an appointment that can still happen leaves the patient expecting an action."""
    return status in UPCOMING_STATUSES
