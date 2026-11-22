"""Section 14: GET /slots. Public; a session, when present, only widens what staff may see."""

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure
from scheduling.domain.free_slots import TimeRange
from scheduling.models import User
from scheduling.use_cases.free_slots_query import find_free_slots
from scheduling.use_cases.schedule_loading import online_only_for
from scheduling.views.access import public
from scheduling.views.api_view import ApiView
from scheduling.views.booking_schemas import (
    SlotsQuery,
    refuse_empty_range,
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
        refused = refuse_empty_range(values)
        if refused is not None:
            return failure_response(refused)
        window = TimeRange(required_instant(values, "from"), required_instant(values, "to"))
        user = request.user
        result = find_free_slots(
            required_uuid(values, "appointment_type_id"),
            uuid_of(values, "clinician_id"),
            window,
            online_only_for(user if isinstance(user, User) else None),
        )
        if isinstance(result, Failure):
            return failure_response(result)
        return Response(slots_body(result.value))
