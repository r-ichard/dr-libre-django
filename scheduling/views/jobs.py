"""Section 14: POST /jobs/reminders, admin only; the same use case the worker runs."""

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure
from scheduling.domain.vocabulary import Role
from scheduling.use_cases.reminders import send_reminders
from scheduling.views.access import roles, signed_in_user
from scheduling.views.api_view import ApiView
from scheduling.views.booking_schemas import NoFieldsRequest
from scheduling.views.failure_response import failure_response
from scheduling.views.schemas import validate_body


class RemindersView(ApiView):
    permission_classes = roles(Role.ADMIN)

    def post(self, request: Request) -> Response:
        body = validate_body(NoFieldsRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        return Response({"reminder_count": send_reminders(signed_in_user(request))})
