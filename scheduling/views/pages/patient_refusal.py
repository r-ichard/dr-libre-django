"""A refused cancel or reschedule as a page with the reason and a way forward."""

from django.http import HttpRequest, HttpResponse

from scheduling.domain.booking_refusals import refusal_for
from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.portal_options import appointment_options
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.models import Appointment, User
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.page_view import render_page
from scheduling.views.pages.patient_rows import LIST_PATH

HEADING = "This change was not made"
STATUS_CHANGED = "The status of this appointment no longer allows this change."
LIST_ACTION = (LIST_PATH, "Back to your appointments")
OFFER_CLOSED = "This offer is no longer open."
WAITLIST_ACTION = ("/patient/waitlist", "Back to your waitlist")


def change_refused_page(
    request: HttpRequest,
    failure: Failure,
    user: User,
    times_action: tuple[str, str] = LIST_ACTION,
    back_action: tuple[str, str] = LIST_ACTION,
) -> HttpResponse:
    """times_action is where a taken slot leads; every other refusal leads to back_action."""
    refusal = refusal_for(failure)
    status_changed = failure.code == FailureCode.INVALID_TRANSITION
    message = STATUS_CHANGED if status_changed else refusal.message
    http_status = 409 if status_changed else refusal.status
    href, text = (
        times_action if refusal.way_forward == "times" and not status_changed else back_action
    )
    return message_page(request, user, message, (href, text), http_status)


def blocked_page_or_none(
    request: HttpRequest, appointment: Appointment, user: User, action: str
) -> HttpResponse | None:
    """The rules say no before a form is shown: give the reason and the hospital's phone."""
    options = appointment_options(
        AppointmentStatus(appointment.status),
        appointment.starts_at,
        current_request_context().now,
        appointment.appointment_type.is_bookable_online,
    )
    option = options.cancel if action == "cancel" else options.reschedule
    if option.allowed:
        return None
    hospital = appointment.appointment_type.department.hospital
    message = f"{option.reason} Call {hospital.name} on {hospital.phone}."
    return message_page(request, user, message, LIST_ACTION, 409)


def message_page(
    request: HttpRequest, user: User, message: str, action: tuple[str, str], status: int
) -> HttpResponse:
    context = {
        "heading": HEADING,
        "message": message,
        "action_href": action[0],
        "action_text": action[1],
    }
    return render_page(request, "booking/refused.html", context, status=status, signed_in_user=user)


def waitlist_refused_page(request: HttpRequest, failure: Failure, user: User) -> HttpResponse:
    """An accept that failed leaves the entry as it was; every way forward is the waitlist."""
    status_changed = failure.code == FailureCode.INVALID_TRANSITION
    refusal = refusal_for(failure)
    message = OFFER_CLOSED if status_changed else refusal.message
    http_status = 409 if status_changed else refusal.status
    return message_page(request, user, message, WAITLIST_ACTION, http_status)
