import logging
from collections.abc import Mapping

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from scheduling.domain.failure import Failure, FailureCode, FieldMessage
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.schemas import field_messages

logger = logging.getLogger("drlibre.failure")

INTERNAL_ERROR_CODE = "internal_error"
INTERNAL_ERROR_STATUS = 500
INTERNAL_ERROR_MESSAGE = "Something went wrong."

STATUS_BY_CODE: dict[FailureCode, int] = {
    FailureCode.INVALID_INPUT: 400,
    FailureCode.UNAUTHENTICATED: 401,
    FailureCode.FORBIDDEN: 403,
    FailureCode.NOT_FOUND: 404,
    FailureCode.CONFLICT: 409,
    FailureCode.NO_ROOM_AVAILABLE: 409,
    FailureCode.NO_CLINICIAN_AVAILABLE: 409,
    FailureCode.INVALID_TRANSITION: 409,
    FailureCode.HAS_DEPENDENTS: 409,
    FailureCode.RULE_VIOLATION: 422,
    FailureCode.RATE_LIMITED: 429,
}

MESSAGE_BY_CODE: dict[FailureCode, str] = {
    FailureCode.INVALID_INPUT: "The request is not valid.",
    FailureCode.UNAUTHENTICATED: "Authentication is required.",
    FailureCode.FORBIDDEN: "You are not allowed to do this.",
    FailureCode.NOT_FOUND: "Not found.",
    FailureCode.CONFLICT: "The request conflicts with existing data.",
    FailureCode.NO_ROOM_AVAILABLE: "No room is available.",
    FailureCode.NO_CLINICIAN_AVAILABLE: "No clinician is available.",
    FailureCode.INVALID_TRANSITION: "The status change is not allowed.",
    FailureCode.HAS_DEPENDENTS: "Other records depend on this one.",
    FailureCode.RULE_VIOLATION: "A booking rule was violated.",
    FailureCode.RATE_LIMITED: "Too many requests.",
}


class ErrorResponse(Response):
    renderer_context: dict[str, object]


def failure_response(failure: Failure) -> Response:
    return error_response(
        failure.code.value,
        STATUS_BY_CODE[failure.code],
        MESSAGE_BY_CODE[failure.code],
        failure.details,
    )


def error_response(code: str, status: int, message: str, details: dict[str, object]) -> Response:
    error = {
        "code": code,
        "message": message,
        "correlation_id": current_request_context().correlation_id,
        "details": details,
    }
    response = ErrorResponse({"error": error}, status=status)
    response.accepted_renderer = JSONRenderer()
    response.accepted_media_type = JSONRenderer.media_type
    response.renderer_context = {}
    return response


def handle_exception(exc: Exception, context: Mapping[str, object]) -> Response:
    """DRF exception hook. Unexpected errors are logged with trace and answered generically."""
    failure = failure_from_exception(exc)
    if failure is not None:
        return failure_response(failure)
    logger.error("unexpected error", exc_info=exc)
    return error_response(INTERNAL_ERROR_CODE, INTERNAL_ERROR_STATUS, INTERNAL_ERROR_MESSAGE, {})


def failure_from_exception(exc: Exception) -> Failure | None:
    if isinstance(exc, exceptions.ValidationError):
        return Failure.invalid_input(field_messages(exc.detail))
    if isinstance(exc, exceptions.ParseError | exceptions.UnsupportedMediaType):
        return Failure.invalid_input([FieldMessage("body", "The request body is not readable.")])
    if isinstance(exc, Http404 | exceptions.NotFound | exceptions.MethodNotAllowed):
        return Failure.not_found()
    if isinstance(exc, exceptions.NotAuthenticated | exceptions.AuthenticationFailed):
        return Failure.unauthenticated()
    if isinstance(exc, DjangoPermissionDenied | exceptions.PermissionDenied):
        return Failure.forbidden()
    return None
