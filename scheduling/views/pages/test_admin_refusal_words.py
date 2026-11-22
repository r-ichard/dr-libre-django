"""Task 20, item 5: every refusal names what is wrong in words, with a status and a way back."""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from scheduling.domain.booking_rules import BookingRule
from scheduling.domain.failure import Failure
from scheduling.models import User
from scheduling.models.builders import make
from scheduling.views.pages.admin_refusal import admin_refused_page
from scheduling.views.pages.patient_refusal import change_refused_page

pytestmark = pytest.mark.django_db

ROOM_WORDS = "The room is already in use then."
PATIENT_WORDS = "The patient has another appointment then."
CLINICIAN_WORDS = "The clinician is no longer free then."
STALE_WORDS = "The status changed since this page was opened. Open the record again."


@pytest.mark.parametrize(
    ("resource", "words"),
    [("room", ROOM_WORDS), ("patient", PATIENT_WORDS), ("clinician", CLINICIAN_WORDS)],
)
def returns_409_with_the_resource_words_when_a_resource_is_busy(resource: str, words: str) -> None:
    user = make("User", role="ADMIN")
    assert isinstance(user, User)
    request = RequestFactory().get("/admin-console/waitlist")

    response = admin_refused_page(
        request, user, Failure.conflict([resource]), ("/admin-console/waitlist", "Back")
    )

    assert response.status_code == 409
    assert words in response.content.decode()


BOOKING_PAGE_CALLERS = [
    ("admin", "ADMIN"),
    ("change_refused_page", "PATIENT"),
    ("change_refused_page", "CLINICIAN"),
]


def _booking_page(caller: str, user: User, failure: Failure) -> HttpResponse:
    request = RequestFactory().get("/")
    back = ("/", "Back")
    if caller == "admin":
        return admin_refused_page(request, user, failure, back)
    return change_refused_page(request, failure, user, back_action=back)


RULE_SENTENCES = [
    (BookingRule.LEAD_TIME_TOO_SHORT, "Appointments must start at least 2 hours from now."),
    (BookingRule.TOO_MANY_OPEN_BOOKINGS, "You already have 3 upcoming online bookings."),
    (BookingRule.TYPE_NOT_BOOKABLE_ONLINE, "This appointment type cannot be booked online."),
    (BookingRule.CANCELLATION_WINDOW_CLOSED, "This appointment is too close to change online."),
    (BookingRule.START_IN_THE_PAST, "That time has already passed."),
    (BookingRule.OUTSIDE_AVAILABILITY, "That time is not offered. Choose one from the week."),
]


@pytest.mark.parametrize(("rule", "sentence"), RULE_SENTENCES)
@pytest.mark.parametrize(("caller", "role"), BOOKING_PAGE_CALLERS)
def returns_the_rule_sentence_and_no_code_on_every_booking_page_for_every_rule(
    rule: BookingRule, sentence: str, caller: str, role: str
) -> None:
    user = make("User", role=role)
    assert isinstance(user, User)

    body = _booking_page(caller, user, Failure.rule_violation([rule])).content.decode()

    assert sentence in body and rule.value not in body


@pytest.mark.parametrize(
    ("current_status", "action_phrase", "sentence"),
    [
        ("BOOKED", "completed", "This appointment is booked, so it cannot be completed."),
        ("CHECKED_IN", "checked in", "This appointment is checked in, so it cannot be checked in."),
        ("COMPLETED", "cancelled", "This appointment is completed, so it cannot be cancelled."),
    ],
)
def returns_the_status_sentence_when_status_action_is_not_allowed(
    current_status: str, action_phrase: str, sentence: str
) -> None:
    user = make("User", role="ADMIN")
    assert isinstance(user, User)
    request = RequestFactory().get("/admin-console/appointments")

    response = admin_refused_page(
        request,
        user,
        Failure.invalid_transition(current_status),
        ("/admin-console/appointments", "Back"),
        action_phrase=action_phrase,
    )

    body = response.content.decode()
    assert response.status_code == 409 and sentence in body
    assert "changed since" not in body


def returns_the_stale_sentence_when_the_status_is_not_an_appointment_status() -> None:
    user = make("User", role="ADMIN")
    assert isinstance(user, User)
    request = RequestFactory().get("/admin-console/appointments")

    response = admin_refused_page(
        request,
        user,
        Failure.invalid_transition("OFFERED"),
        ("/admin-console/appointments", "Back"),
        action_phrase="completed",
    )

    assert response.status_code == 409
    assert STALE_WORDS in response.content.decode()


def returns_the_stale_sentence_when_no_action_is_named() -> None:
    user = make("User", role="ADMIN")
    assert isinstance(user, User)
    request = RequestFactory().get("/admin-console/waitlist")

    response = admin_refused_page(
        request, user, Failure.invalid_transition("BOOKED"), ("/admin-console/waitlist", "Back")
    )

    assert response.status_code == 409
    assert STALE_WORDS in response.content.decode()
