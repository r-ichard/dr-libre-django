"""Section 10: a refusal of an admin action as a page with the reason and a way forward. The
words of a taken slot or a closed status are the admin's; the rest come from the booking steps."""

from django.http import Http404, HttpRequest, HttpResponse

from scheduling.domain.booking_refusals import refusal_for
from scheduling.domain.failure import Failure, FailureCode
from scheduling.models import User
from scheduling.views.pages.page_view import render_page
from scheduling.views.pages.patient_refusal import message_page

STATUS_CHANGED = "The status changed since this page was opened. Open the record again."
OFFER_HELD = "Another entry already holds that offer."
NO_CANCELLED_TIME = (
    "No cancelled time of this type falls inside the window. "
    "If one does, its clinician is no longer free then."
)
NO_ROOM = "No room is free then."
BUSY_WORDS = {
    "clinician": "The clinician is no longer free then.",
    "room": "The room is already in use then.",
    "patient": "The patient has another appointment then.",
}


def admin_refused_page(
    request: HttpRequest,
    user: User,
    failure: Failure,
    back: tuple[str, str],
    *,
    waitlist_offer: bool = False,
) -> HttpResponse:
    """`back` is where every refusal leads: the record, the week strip or the list."""
    code = failure.code
    if code == FailureCode.NOT_FOUND:
        raise Http404
    if code == FailureCode.FORBIDDEN:
        return render_page(request, "errors/403.html", status=403, signed_in_user=user)
    message, status = _message_and_status(failure, waitlist_offer)
    return message_page(request, user, message, back, status)


def _message_and_status(failure: Failure, waitlist_offer: bool) -> tuple[str, int]:
    code = failure.code
    if code == FailureCode.INVALID_TRANSITION:
        return STATUS_CHANGED, 409
    if code == FailureCode.NO_ROOM_AVAILABLE:
        return NO_ROOM, 409
    if code == FailureCode.NO_CLINICIAN_AVAILABLE and waitlist_offer:
        return NO_CANCELLED_TIME, 409
    if code == FailureCode.CONFLICT:
        resources = failure.details.get("resources")
        named = [str(name) for name in resources] if isinstance(resources, list) else []
        words = [OFFER_HELD if name == "offer" else BUSY_WORDS.get(name, "") for name in named]
        return " ".join(word for word in words if word) or refusal_for(failure).message, 409
    refusal = refusal_for(failure)
    return refusal.message, refusal.status
