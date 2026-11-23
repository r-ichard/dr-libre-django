"""The patient's appointment lists and the cancel step. The patient comes from the
session; the record rule answers 404 for a missing appointment and 403 for someone else's."""

from math import ceil
from uuid import UUID

from django.http import Http404, HttpRequest, HttpResponse

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.vocabulary import Role
from scheduling.models import Appointment
from scheduling.use_cases.appointment_changes import cancel_appointment
from scheduling.use_cases.patient_appointments import (
    own_appointment,
    past_appointments,
    upcoming_appointments,
)
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.booking_schemas import CANCELLATION_REASON_MAXIMUM, CancelRequest
from scheduling.views.pages.booking_links import path_uuid
from scheduling.views.pages.page_view import PageView, render_page
from scheduling.views.pages.patient_refusal import blocked_page_or_none, change_refused_page
from scheduling.views.pages.patient_rows import LIST_PATH, appointment_row
from scheduling.views.pages.portal_forms import forget_notice, redirect_with_notice, take_notice
from scheduling.views.schemas import validate_body

PAGE_SIZE = 10
MAXIMUM_PAGE_DIGITS = 6
NOTICES = {
    "cancelled": "Your appointment is cancelled.",
    "booked": "Your waitlist slot is booked.",
    "rescheduled": "Your appointment has a new time.",
}
REASON_REQUIRED = "Enter a reason for cancelling."
REASON_TOO_LONG = f"Keep the reason under {CANCELLATION_REASON_MAXIMUM} characters."


class AppointmentsPage(PageView):
    template_name = "patient/appointments.html"
    allowed_roles = frozenset({Role.PATIENT})

    def get(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        now = current_request_context().now
        page = page_number(request.GET.get("page", ""))
        past = past_appointments(self.user, now, page, PAGE_SIZE)
        page_count = max(1, ceil(past.count / PAGE_SIZE))
        context = {
            "notice": take_notice(request, NOTICES),
            "upcoming": [
                appointment_row(item, now) for item in upcoming_appointments(self.user, now)
            ],
            "past": [appointment_row(item, now) for item in past.rows],
            "page": page,
            "page_count": page_count,
            "previous_href": f"{LIST_PATH}?page={page - 1}" if page > 1 else "",
            "next_href": f"{LIST_PATH}?page={page + 1}" if page < page_count else "",
        }
        return forget_notice(request, self.page(request, context))


class OwnAppointmentPage(PageView):
    """A page about one appointment; subclasses ask for it through `appointment_or_refusal`."""

    allowed_roles = frozenset({Role.PATIENT})

    def appointment_or_refusal(self, request: HttpRequest) -> Appointment | HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = own_appointment(path_uuid(self, "appointment_id"), self.user)
        if isinstance(found, Failure):
            if found.code == FailureCode.NOT_FOUND:
                raise Http404
            return render_page(request, "errors/403.html", status=403, signed_in_user=self.user)
        return found.value


class CancelPage(OwnAppointmentPage):
    template_name = "patient/cancel.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        blocked = blocked_page_or_none(request, found, self.user, "cancel")
        if blocked is not None:
            return blocked
        return self._form(request, found, "", "")

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        reason = request.POST.get("reason", "").strip()
        error = reason_error(reason)
        if error:
            return self._form(request, found, reason, error, 422)
        cancelled = cancel_appointment(UUID(str(found.pk)), reason, self.user)
        if isinstance(cancelled, Failure):
            return change_refused_page(request, cancelled, self.user)
        return redirect_with_notice(LIST_PATH, "cancelled")

    def _form(
        self,
        request: HttpRequest,
        appointment: Appointment,
        reason: str,
        error: str,
        status: int = 200,
    ) -> HttpResponse:
        now = current_request_context().now
        row = appointment_row(appointment, now)
        context = {
            "row": row,
            "reason": reason,
            "error": error,
            "cancel_errors": [{"target": "id_reason", "message": error}],
            "action": request.path,
            "list_path": LIST_PATH,
        }
        return self.page(request, context, status)


def reason_error(reason: str) -> str:
    if not reason:
        return REASON_REQUIRED
    checked = validate_body(CancelRequest, {"reason": reason})
    return REASON_TOO_LONG if isinstance(checked, Failure) else ""


def page_number(raw: str) -> int:
    readable = raw.isascii() and raw.isdigit() and len(raw) <= MAXIMUM_PAGE_DIGITS
    return max(1, int(raw)) if readable else 1
