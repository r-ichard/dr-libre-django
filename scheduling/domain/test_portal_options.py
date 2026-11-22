"""Task 14: what a patient may do with an appointment, and the plain words when not."""

from datetime import UTC, datetime, timedelta

from scheduling.domain.booking_rules import CANCELLATION_WINDOW
from scheduling.domain.portal_options import appointment_options, expects_change_hint, is_upcoming
from scheduling.domain.vocabulary import AppointmentStatus

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
IN_25_HOURS = NOW + timedelta(hours=25)


def returns_both_allowed_when_booked_and_starts_in_25_hours() -> None:
    options = appointment_options(AppointmentStatus.BOOKED, IN_25_HOURS, NOW)

    assert (options.cancel.allowed, options.reschedule.allowed) == (True, True)


def returns_cancel_allowed_when_start_is_exactly_24_hours_away() -> None:
    options = appointment_options(AppointmentStatus.BOOKED, NOW + CANCELLATION_WINDOW, NOW)

    assert options.cancel.allowed is True


def returns_reschedule_refused_with_type_sentence_when_type_not_bookable_online() -> None:
    options = appointment_options(
        AppointmentStatus.BOOKED, IN_25_HOURS, NOW, type_bookable_online=False
    )

    assert options.reschedule.allowed is False
    assert options.reschedule.reason == "This appointment type cannot be booked online."
    assert options.cancel.allowed is True


def returns_less_than_24_hours_reason_when_start_is_one_minute_inside_window() -> None:
    start = NOW + CANCELLATION_WINDOW - timedelta(minutes=1)

    options = appointment_options(AppointmentStatus.BOOKED, start, NOW)

    assert options.cancel.allowed is False
    assert "less than 24 hours" in options.cancel.reason
    assert options.reschedule.allowed is False
    assert "less than 24 hours" in options.reschedule.reason


def returns_started_reason_when_start_is_now() -> None:
    options = appointment_options(AppointmentStatus.BOOKED, NOW, NOW)

    assert options.cancel.allowed is False
    assert "already started" in options.cancel.reason


def returns_cancelled_reason_when_cancelled() -> None:
    options = appointment_options(AppointmentStatus.CANCELLED, IN_25_HOURS, NOW)

    assert options.cancel.allowed is False
    assert "already cancelled" in options.cancel.reason
    assert "already cancelled" in options.reschedule.reason


def returns_checked_in_reason_for_reschedule_only_when_checked_in() -> None:
    options = appointment_options(AppointmentStatus.CHECKED_IN, IN_25_HOURS, NOW)

    assert options.cancel.allowed is True
    assert options.reschedule.allowed is False
    assert "checked in" in options.reschedule.reason


def returns_no_option_when_completed() -> None:
    options = appointment_options(AppointmentStatus.COMPLETED, NOW - timedelta(days=2), NOW)

    assert (options.cancel.allowed, options.reschedule.allowed) == (False, False)
    assert "already took place" in options.cancel.reason


def returns_upcoming_when_active_status_and_start_is_in_the_future() -> None:
    answers = [
        is_upcoming(status, IN_25_HOURS, NOW)
        for status in (
            AppointmentStatus.BOOKED,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.CHECKED_IN,
        )
    ]

    assert answers == [True, True, True]


def returns_not_upcoming_when_start_equals_now_or_status_is_final() -> None:
    answers = [
        is_upcoming(AppointmentStatus.BOOKED, NOW, NOW),
        is_upcoming(AppointmentStatus.CANCELLED, IN_25_HOURS, NOW),
        is_upcoming(AppointmentStatus.COMPLETED, IN_25_HOURS, NOW),
        is_upcoming(AppointmentStatus.NO_SHOW, IN_25_HOURS, NOW),
    ]

    assert answers == [False, False, False, False]


def returns_took_place_reason_when_no_show() -> None:
    options = appointment_options(AppointmentStatus.NO_SHOW, NOW - timedelta(days=2), NOW)

    assert (options.cancel.allowed, options.reschedule.allowed) == (False, False)
    assert options.cancel.reason == "This appointment already took place."


def returns_empty_reasons_when_both_changes_are_allowed() -> None:
    options = appointment_options(AppointmentStatus.CONFIRMED, IN_25_HOURS, NOW)

    assert (options.cancel.reason, options.reschedule.reason) == ("", "")


def returns_change_hint_only_when_status_is_upcoming() -> None:
    answers = {status: expects_change_hint(status) for status in AppointmentStatus}

    assert {status for status, hinted in answers.items() if hinted} == {
        AppointmentStatus.BOOKED,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CHECKED_IN,
    }
