"""Task 22, spec 15.1: every answer under /fhir is FHIR JSON carrying an OperationOutcome on
failure, never the application API's error body and never an HTML page."""

import json

from django.http import HttpResponse

from scheduling.domain.failure import Failure
from scheduling.domain.fhir_clean import without_empty
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_outcome import failure_outcome, operation_outcome
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.failure_response import (
    INTERNAL_ERROR_MESSAGE,
    INTERNAL_ERROR_STATUS,
    MESSAGE_BY_CODE,
    STATUS_BY_CODE,
)

FHIR_CONTENT_TYPE = "application/fhir+json; charset=utf-8"
NOT_ACCEPTABLE_STATUS = 406
METHOD_NOT_ALLOWED_STATUS = 405
METHOD_NOT_ALLOWED_MESSAGE = "This interaction is not supported; only GET is."
NOT_ACCEPTABLE_MESSAGE = "Only application/fhir+json is served."


def resource_response(resource: Resource, status: int = 200) -> HttpResponse:
    return HttpResponse(
        json.dumps(without_empty(resource)), status=status, content_type=FHIR_CONTENT_TYPE
    )


def failure_response(failure: Failure) -> HttpResponse:
    outcome = failure_outcome(
        failure, MESSAGE_BY_CODE[failure.code], current_request_context().correlation_id
    )
    return resource_response(outcome, STATUS_BY_CODE[failure.code])


def not_acceptable_response() -> HttpResponse:
    outcome = operation_outcome(
        "not-supported", NOT_ACCEPTABLE_MESSAGE, current_request_context().correlation_id
    )
    return resource_response(outcome, NOT_ACCEPTABLE_STATUS)


def method_not_allowed_response() -> HttpResponse:
    outcome = operation_outcome(
        "not-supported", METHOD_NOT_ALLOWED_MESSAGE, current_request_context().correlation_id
    )
    response = resource_response(outcome, METHOD_NOT_ALLOWED_STATUS)
    response["Allow"] = "GET"
    return response


def internal_error_response() -> HttpResponse:
    outcome = operation_outcome(
        "exception", INTERNAL_ERROR_MESSAGE, current_request_context().correlation_id
    )
    return resource_response(outcome, INTERNAL_ERROR_STATUS)
