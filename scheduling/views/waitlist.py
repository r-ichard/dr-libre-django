"""Section 14: join, offer and accept on the waitlist. The actor is the session's user."""

from uuid import UUID

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure, Result
from scheduling.models import WaitlistEntry
from scheduling.use_cases.waitlist import accept_offer, join_waitlist, offer_waitlist_entry
from scheduling.views.access import signed_in, signed_in_user
from scheduling.views.api_view import ApiView
from scheduling.views.booking_schemas import NoFieldsRequest
from scheduling.views.failure_response import failure_response
from scheduling.views.schemas import validate_body
from scheduling.views.waitlist_schemas import JoinRequest, join_command_of, waitlist_entry_body


class WaitlistView(ApiView):
    permission_classes = signed_in()

    def post(self, request: Request) -> Response:
        body = validate_body(JoinRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        joined = join_waitlist(join_command_of(body.value), signed_in_user(request))
        return _entry_response(joined, 201)


class AcceptView(ApiView):
    permission_classes = signed_in()

    def post(self, request: Request, entry_id: UUID) -> Response:
        body = validate_body(NoFieldsRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        return _entry_response(accept_offer(entry_id, signed_in_user(request)), 200)


class OfferView(ApiView):
    permission_classes = signed_in()

    def post(self, request: Request, entry_id: UUID) -> Response:
        body = validate_body(NoFieldsRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        return _entry_response(offer_waitlist_entry(entry_id, signed_in_user(request)), 200)


def _entry_response(changed: Result[WaitlistEntry], status: int) -> Response:
    if isinstance(changed, Failure):
        return failure_response(changed)
    return Response(waitlist_entry_body(changed.value), status=status)
