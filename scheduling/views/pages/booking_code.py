"""The visitor's code step: proves the email, then the held slot becomes an appointment."""

from uuid import UUID

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.failure import Failure, FailureCode
from scheduling.use_cases.booking_holds import resend_code
from scheduling.use_cases.booking_page_data import HoldSummary, hold_summary
from scheduling.use_cases.booking_verification import verify_hold
from scheduling.views.hold_cookie import made_this_hold
from scheduling.views.hold_schemas import VerifyRequest
from scheduling.views.network_address import network_address
from scheduling.views.pages.booking_links import (
    code_href,
    confirmation_href,
    path_uuid,
    resend_href,
)
from scheduling.views.pages.booking_refusal import WayBack, refused_page
from scheduling.views.pages.page_view import PageView
from scheduling.views.schemas import validate_body
from scheduling.views.session_cookie import set_session_cookie

CODE_FORMAT_MESSAGE = "Enter the 6 digit code."
NO_TRIES_MESSAGE = "That code is not right or has expired. Send a new code to try again."


def wrong_code_message(attempts_left: int) -> str:
    if attempts_left <= 0:
        return NO_TRIES_MESSAGE
    tries = "1 try" if attempts_left == 1 else f"{attempts_left} tries"
    return f"That code is not right. You have {tries} left."


class CodePage(PageView):
    template_name = "booking/code.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        hold_id = path_uuid(self, "hold_id")
        summary = hold_summary(hold_id)
        if summary is None or not made_this_hold(request, hold_id):
            return self._expired(request)
        return self._code_form(request, hold_id, summary, "", request.GET.get("sent") == "1")

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        hold_id = path_uuid(self, "hold_id")
        summary = hold_summary(hold_id)
        if summary is None or not made_this_hold(request, hold_id):
            return self._expired(request)
        body = validate_body(VerifyRequest, {"code": request.POST.get("code", "").strip()})
        if isinstance(body, Failure):
            message = body.field_messages[0].message if body.field_messages else CODE_FORMAT_MESSAGE
            return self._code_form(request, hold_id, summary, message, False, 422)
        user_agent = request.headers.get("User-Agent", "")
        verified = verify_hold(hold_id, str(body.value["code"]), user_agent)
        if isinstance(verified, Failure):
            return self._verify_refused(request, hold_id, summary, verified)
        response = HttpResponseRedirect(
            confirmation_href(verified.value.appointment.pk), status=303
        )
        set_session_cookie(response, verified.value.token, verified.value.session_expires_at)
        return response

    def _verify_refused(
        self, request: HttpRequest, hold_id: UUID, summary: HoldSummary, failure: Failure
    ) -> HttpResponse:
        if failure.code == FailureCode.INVALID_INPUT:
            fresh = hold_summary(hold_id)
            if fresh is None:
                return self._expired(request)
            message = wrong_code_message(fresh.attempts_left)
            return self._code_form(request, hold_id, fresh, message, False, 422)
        way_back = WayBack(summary.appointment_type_id, summary.pinned_clinician_id, request.path)
        return refused_page(request, failure, way_back, None)

    def _expired(self, request: HttpRequest) -> HttpResponse:
        return refused_page(request, Failure.not_found(), WayBack(), None)

    def _code_form(
        self,
        request: HttpRequest,
        hold_id: UUID,
        summary: HoldSummary,
        error: str,
        sent: bool,
        status: int = 200,
    ) -> HttpResponse:
        context = {
            "masked_email": summary.masked_email,
            "error": error,
            "code_errors": [{"target": "id_code", "message": error}],
            "sent": sent,
            "resend_action": resend_href(hold_id),
            "action": code_href(hold_id),
        }
        return self.page(request, context, status)


class ResendPage(PageView):
    form_page = "/book/holds/{hold_id}/code"
    http_method_names = ["post"]

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        hold_id = path_uuid(self, "hold_id")
        if not made_this_hold(request, hold_id):
            return refused_page(request, Failure.not_found(), WayBack(), None)
        summary = hold_summary(hold_id)
        resent = resend_code(hold_id, network_address(request))
        if isinstance(resent, Failure):
            way_back = WayBack(
                summary.appointment_type_id if summary else None,
                summary.pinned_clinician_id if summary else None,
                code_href(hold_id),
            )
            return refused_page(request, resent, way_back, None)
        return HttpResponseRedirect(f"{code_href(hold_id)}?sent=1", status=303)
