"""Section 7.1: every refusal of a booking step as a message and a way forward."""

from dataclasses import dataclass
from typing import Literal

from scheduling.domain.booking_rules import LEAD_TIME, OPEN_ONLINE_BOOKINGS_MAXIMUM, BookingRule
from scheduling.domain.failure import Failure, FailureCode

type WayForward = Literal["times", "start", "retry", "wait"]

SLOT_TAKEN = "That time was just taken."
MINUTES_PER_HOUR = 60


@dataclass(frozen=True)
class Refusal:
    message: str
    way_forward: WayForward
    status: int


def refusal_for(failure: Failure) -> Refusal:
    code = failure.code
    if code == FailureCode.RULE_VIOLATION:
        return _rule_refusal(failure)
    if code == FailureCode.RATE_LIMITED:
        return Refusal("Too many tries. Wait an hour and try again.", "wait", 429)
    if code == FailureCode.MAIL_UNAVAILABLE:
        return Refusal("We could not send the email. Try again in a few minutes.", "retry", 503)
    if code == FailureCode.NOT_FOUND:
        return Refusal("This booking has expired. Start again.", "start", 404)
    if code == FailureCode.FORBIDDEN:
        return Refusal(
            "We could not book this appointment online. Contact the hospital.", "start", 403
        )
    return Refusal(SLOT_TAKEN, "times", 409)


def _rule_refusal(failure: Failure) -> Refusal:
    violated = failure.details.get("violated_rules")
    rules = violated if isinstance(violated, list) else []
    for rule in rules:
        sentence = _RULE_SENTENCES.get(rule)
        if sentence is not None:
            return Refusal(sentence, "times", 422)
    return Refusal(SLOT_TAKEN, "times", 409)


_LEAD_HOURS = int(LEAD_TIME.total_seconds() // (MINUTES_PER_HOUR * MINUTES_PER_HOUR))
_RULE_SENTENCES: dict[str, str] = {
    BookingRule.LEAD_TIME_TOO_SHORT: (
        f"Appointments must start at least {_LEAD_HOURS} hours from now."
    ),
    BookingRule.TOO_MANY_OPEN_BOOKINGS: (
        f"You already have {OPEN_ONLINE_BOOKINGS_MAXIMUM} upcoming online bookings."
    ),
    BookingRule.TYPE_NOT_BOOKABLE_ONLINE: "This appointment type cannot be booked online.",
    BookingRule.CANCELLATION_WINDOW_CLOSED: "This appointment is too close to change online.",
}
