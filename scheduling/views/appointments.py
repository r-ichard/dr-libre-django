"""Section 14: GET and POST /appointments. The actor is the session's user, never the body."""

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure
from scheduling.use_cases.appointment_list import list_appointments
from scheduling.use_cases.placement import place_appointment
from scheduling.views.access import signed_in, signed_in_user
from scheduling.views.api_view import ApiView
from scheduling.views.booking_schemas import (
    AppointmentsQuery,
    BookRequest,
    appointment_body,
    filters_of,
    placement_command_of,
    refuse_empty_range,
)
from scheduling.views.failure_response import failure_response
from scheduling.views.schemas import validate_body


class AppointmentsView(ApiView):
    permission_classes = signed_in()

    def get(self, request: Request) -> Response:
        query = validate_body(AppointmentsQuery, request.query_params)
        if isinstance(query, Failure):
            return failure_response(query)
        refused = refuse_empty_range(query.value)
        if refused is not None:
            return failure_response(refused)
        page, page_size = int(str(query.value["page"])), int(str(query.value["page_size"]))
        found = list_appointments(signed_in_user(request), filters_of(query.value), page, page_size)
        return Response(
            {
                "count": found.count,
                "page": page,
                "page_size": page_size,
                "results": [appointment_body(row) for row in found.rows],
            }
        )

    def post(self, request: Request) -> Response:
        body = validate_body(BookRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        placed = place_appointment(placement_command_of(body.value), signed_in_user(request))
        if isinstance(placed, Failure):
            return failure_response(placed)
        return Response(appointment_body(placed.value), status=201)
