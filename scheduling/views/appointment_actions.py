"""Section 14: cancel, reschedule and the status actions of one appointment. The actor is the
session's user, never the body."""

from uuid import UUID

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure, Result
from scheduling.domain.vocabulary import AppointmentStatus, Role
from scheduling.models import Appointment
from scheduling.use_cases.appointment_changes import (
    cancel_appointment,
    change_status,
    reschedule_appointment,
)
from scheduling.views.access import roles, signed_in, signed_in_user
from scheduling.views.api_view import ApiView
from scheduling.views.booking_schemas import (
    CancelRequest,
    NoFieldsRequest,
    RescheduleRequest,
    appointment_body,
    required_instant,
)
from scheduling.views.failure_response import failure_response
from scheduling.views.schemas import validate_body


class CancelView(ApiView):
    permission_classes = signed_in()

    def post(self, request: Request, appointment_id: UUID) -> Response:
        body = validate_body(CancelRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        reason = str(body.value["reason"])
        changed = cancel_appointment(appointment_id, reason, signed_in_user(request))
        return _changed_response(changed)


class RescheduleView(ApiView):
    permission_classes = signed_in()

    def post(self, request: Request, appointment_id: UUID) -> Response:
        body = validate_body(RescheduleRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        starts_at = required_instant(body.value, "starts_at")
        changed = reschedule_appointment(appointment_id, starts_at, signed_in_user(request))
        return _changed_response(changed)


class StatusActionView(ApiView):
    permission_classes = roles(Role.CLINICIAN, Role.ADMIN)
    target: AppointmentStatus

    def post(self, request: Request, appointment_id: UUID) -> Response:
        body = validate_body(NoFieldsRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        changed = change_status(appointment_id, self.target, signed_in_user(request))
        return _changed_response(changed)


class CheckInView(StatusActionView):
    target = AppointmentStatus.CHECKED_IN


class CompleteView(StatusActionView):
    target = AppointmentStatus.COMPLETED


class NoShowView(StatusActionView):
    target = AppointmentStatus.NO_SHOW


def _changed_response(changed: Result[Appointment]) -> Response:
    if isinstance(changed, Failure):
        return failure_response(changed)
    return Response(appointment_body(changed.value))
