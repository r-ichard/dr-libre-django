from typing import TYPE_CHECKING

import pytest

from scheduling.domain.booking_rules import BookingRule
from scheduling.domain.failure import Failure, FailureCode

if TYPE_CHECKING:
    from scheduling.domain.booking_refusals import Refusal

TAKEN = "That time was just taken."


def _refusal_for(failure: Failure) -> "Refusal":
    from scheduling.domain.booking_refusals import refusal_for as real

    return real(failure)


def returns_slot_taken_with_link_back_to_times_when_conflict() -> None:
    refusal = _refusal_for(Failure.conflict(["clinician"]))

    assert (refusal.message, refusal.way_forward, refusal.status) == (TAKEN, "times", 409)


@pytest.mark.parametrize(
    "failure",
    [
        Failure.no_clinician_available(),
        Failure.no_room_available(),
    ],
)
def returns_slot_taken_when_the_slot_cannot_be_given(failure: Failure) -> None:
    assert _refusal_for(failure).message == TAKEN


@pytest.mark.parametrize(
    ("rule", "sentence"),
    [
        (BookingRule.LEAD_TIME_TOO_SHORT, "Appointments must start at least 2 hours from now."),
        (BookingRule.TOO_MANY_OPEN_BOOKINGS, "You already have 3 upcoming online bookings."),
        (
            BookingRule.TYPE_NOT_BOOKABLE_ONLINE,
            "This appointment type cannot be booked online.",
        ),
    ],
)
def returns_plain_sentence_when_a_booking_rule_is_violated(
    rule: BookingRule, sentence: str
) -> None:
    refusal = _refusal_for(Failure.rule_violation([rule]))

    assert (refusal.message, refusal.status) == (sentence, 422)


def returns_wait_an_hour_when_rate_limited() -> None:
    refusal = _refusal_for(Failure.rate_limited())

    assert (refusal.message, refusal.status) == ("Too many tries. Wait an hour and try again.", 429)


def returns_try_again_in_a_few_minutes_when_mail_is_unavailable() -> None:
    refusal = _refusal_for(Failure.mail_unavailable())

    assert refusal.message == "We could not send the email. Try again in a few minutes."
    assert refusal.status == 503


def returns_start_again_when_hold_not_found() -> None:
    refusal = _refusal_for(Failure.not_found())

    assert (refusal.way_forward, refusal.status) == ("start", 404)


def returns_a_refusal_when_any_failure_code_can_come_from_booking() -> None:
    codes = [FailureCode.CONFLICT, FailureCode.RATE_LIMITED, FailureCode.MAIL_UNAVAILABLE]

    assert all(_refusal_for(Failure(code)).message for code in codes)


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (Failure.rate_limited(), ("Too many tries. Wait an hour and try again.", "wait", 429)),
        (
            Failure.mail_unavailable(),
            ("We could not send the email. Try again in a few minutes.", "retry", 503),
        ),
        (Failure.not_found(), ("This booking has expired. Start again.", "start", 404)),
        (
            Failure.forbidden(),
            ("We could not book this appointment online. Contact the hospital.", "start", 403),
        ),
        (Failure.conflict(["room"]), (TAKEN, "times", 409)),
        (
            Failure.rule_violation([BookingRule.TYPE_NOT_BOOKABLE_ONLINE]),
            ("This appointment type cannot be booked online.", "times", 422),
        ),
        (
            Failure.rule_violation([BookingRule.CANCELLATION_WINDOW_CLOSED]),
            ("This appointment is too close to change online.", "times", 422),
        ),
        (Failure.rule_violation([]), (TAKEN, "times", 409)),
    ],
)
def returns_message_way_forward_and_status_when_a_failure_is_refused(
    failure: Failure, expected: tuple[str, str, int]
) -> None:
    refusal = _refusal_for(failure)

    assert (refusal.message, refusal.way_forward, refusal.status) == expected


def returns_the_first_known_rule_sentence_when_unknown_rules_come_first() -> None:
    failure = Failure.rule_violation(
        [BookingRule.OUTSIDE_AVAILABILITY, BookingRule.LEAD_TIME_TOO_SHORT]
    )

    assert _refusal_for(failure).status == 422


def returns_slot_taken_when_violated_rules_is_not_a_list() -> None:
    failure = Failure(FailureCode.RULE_VIOLATION, {"violated_rules": "lead_time_too_short"})

    assert _refusal_for(failure).message == TAKEN


def returns_slot_taken_when_violated_rules_are_missing() -> None:
    assert _refusal_for(Failure(FailureCode.RULE_VIOLATION)).message == TAKEN


def returns_not_offered_sentence_when_outside_availability() -> None:
    refusal = _refusal_for(Failure.rule_violation([BookingRule.OUTSIDE_AVAILABILITY]))

    assert (refusal.message, refusal.way_forward, refusal.status) == (
        "That time is not offered. Choose one from the week.",
        "times",
        422,
    )


def returns_passed_sentence_when_start_is_in_the_past() -> None:
    refusal = _refusal_for(Failure.rule_violation([BookingRule.START_IN_THE_PAST]))

    assert (refusal.message, refusal.way_forward, refusal.status) == (
        "That time has already passed.",
        "times",
        422,
    )
