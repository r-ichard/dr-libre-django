"""Section 14: the three hold endpoints. Public: the visitor has no account yet. The answer never
depends on what the address belongs to, and the network address is REMOTE_ADDR only, because a
forwarded header is written by the caller."""

from uuid import UUID

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure
from scheduling.use_cases.booking_holds import create_hold, resend_code
from scheduling.use_cases.booking_verification import verify_hold
from scheduling.views.access import public
from scheduling.views.api_view import ApiView
from scheduling.views.booking_schemas import appointment_body
from scheduling.views.failure_response import failure_response
from scheduling.views.hold_schemas import (
    HoldRequest,
    ResendRequest,
    VerifyRequest,
    hold_body,
    hold_command_of,
)
from scheduling.views.schemas import validate_body
from scheduling.views.session_cookie import set_session_cookie


def _network_address(request: Request) -> str:
    return str(request.META.get("REMOTE_ADDR", ""))


class HoldsView(ApiView):
    permission_classes = public()

    def post(self, request: Request) -> Response:
        body = validate_body(HoldRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        created = create_hold(hold_command_of(body.value), _network_address(request))
        if isinstance(created, Failure):
            return failure_response(created)
        return Response(hold_body(created.value), status=201)


class ResendView(ApiView):
    permission_classes = public()

    def post(self, request: Request, hold_id: UUID) -> Response:
        body = validate_body(ResendRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        resent = resend_code(hold_id, _network_address(request))
        if isinstance(resent, Failure):
            return failure_response(resent)
        return Response(hold_body(resent.value))


class VerifyView(ApiView):
    permission_classes = public()

    def post(self, request: Request, hold_id: UUID) -> Response:
        body = validate_body(VerifyRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        user_agent = request.headers.get("User-Agent", "")
        verified = verify_hold(hold_id, str(body.value["code"]), user_agent)
        if isinstance(verified, Failure):
            return failure_response(verified)
        response = Response(appointment_body(verified.value.appointment), status=201)
        set_session_cookie(response, verified.value.token, verified.value.session_expires_at)
        return response
