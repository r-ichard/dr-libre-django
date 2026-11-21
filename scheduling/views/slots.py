"""Section 14: GET /slots. Public, so no identity is read."""

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure
from scheduling.domain.free_slots import TimeRange
from scheduling.use_cases.free_slots_query import find_free_slots
from scheduling.views.access import public
from scheduling.views.api_view import ApiView
from scheduling.views.booking_schemas import (
    SlotsQuery,
    required_instant,
    required_uuid,
    slots_body,
    uuid_of,
)
from scheduling.views.failure_response import failure_response
from scheduling.views.schemas import validate_body


class SlotsView(ApiView):
    permission_classes = public()

    def get(self, request: Request) -> Response:
        query = validate_body(SlotsQuery, request.query_params)
        if isinstance(query, Failure):
            return failure_response(query)
        values = query.value
        window = TimeRange(required_instant(values, "from"), required_instant(values, "to"))
        result = find_free_slots(
            required_uuid(values, "appointment_type_id"), uuid_of(values, "clinician_id"), window
        )
        if isinstance(result, Failure):
            return failure_response(result)
        return Response(slots_body(result.value))
