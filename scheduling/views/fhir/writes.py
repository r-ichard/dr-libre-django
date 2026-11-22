"""Task 23, spec 15.1: the write side of /fhir. The body is read as JSON, checked as a FHIR resource
of the URL's type and id, and handed to a use case; the answer says what happened as FHIR JSON."""

import json
from uuid import UUID

from django.http import HttpRequest, HttpResponse

from scheduling.domain.failure import Failure, FieldMessage
from scheduling.domain.fhir_body import exact_elements, identity_problem, if_match_version
from scheduling.domain.fhir_common import SPECIALTY_ID, Resource
from scheduling.domain.fhir_outcome import information_outcome
from scheduling.domain.fhir_search import parse_id
from scheduling.domain.fhir_write_shapes import WRITE_SHAPES
from scheduling.domain.write_body import unsupported_media_type
from scheduling.use_cases import fhir_resources
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_specialty_writes import update_specialty_list
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.fhir.responses import (
    failure_response,
    method_not_allowed_response,
    resource_response,
    unsupported_media_response,
    weak_etag,
)

DELETED_MESSAGE = "The record was deleted."
WRITE_MEDIA_TYPES = ("application/json", "application/fhir+json")
BODY_PROBLEM = FieldMessage("body", "The request body is not a JSON object.")


def write(
    request: HttpRequest, resource_type: str, raw_identifier: str | None, caller: Caller
) -> HttpResponse:
    if caller.user is None:
        return failure_response(Failure.unauthenticated())
    if _says_not_json(request):
        return unsupported_media_response()
    refusal = fhir_resources.refusal_before_body(
        resource_type, caller, request.method or "", raw_identifier
    )
    if refusal is not None:
        return failure_response(refusal)
    if resource_type == "CodeSystem":
        return _specialty_list_written(request, raw_identifier, caller)
    identifier = parse_id(raw_identifier) if raw_identifier is not None else None
    if raw_identifier is not None and identifier is None:
        return failure_response(Failure.not_found())
    if (
        identifier is not None
        and request.method in ("PUT", "DELETE")
        and fhir_resources.is_read_only_here(resource_type, UUID(identifier))
    ):
        return method_not_allowed_response(("GET",))
    version = if_match_version(request.headers.get("If-Match"))
    if isinstance(version, Failure):
        return failure_response(version)
    if request.method == "DELETE":
        return _deleted(resource_type, UUID(identifier or ""), caller, version.value)
    body = _checked_body(request, resource_type, identifier)
    if isinstance(body, Failure):
        return failure_response(body)
    if identifier is None:
        return _created(request, resource_type, body, caller)
    result = fhir_resources.update(resource_type, UUID(identifier), body, caller, version.value)
    if isinstance(result, Failure):
        return failure_response(result)
    return _with_etag(resource_response(result.value), result.value)


def _says_not_json(request: HttpRequest) -> bool:
    return (
        unsupported_media_type(
            request.META.get("CONTENT_LENGTH"),
            request.META.get("HTTP_TRANSFER_ENCODING"),
            request.content_type or "",
            WRITE_MEDIA_TYPES,
        )
        is not None
    )


def _specialty_list_written(
    request: HttpRequest, raw_identifier: str | None, caller: Caller
) -> HttpResponse:
    """The one CodeSystem has the id `specialty`, not a UUID, so it skips the UUID routing."""
    if raw_identifier != SPECIALTY_ID:
        return failure_response(Failure.not_found())
    version = if_match_version(request.headers.get("If-Match"))
    if isinstance(version, Failure):
        return failure_response(version)
    body = _checked_body(request, "CodeSystem", SPECIALTY_ID)
    if isinstance(body, Failure):
        return failure_response(body)
    result = update_specialty_list(body, caller, version.value)
    if isinstance(result, Failure):
        return failure_response(result)
    return _with_etag(resource_response(result.value), result.value)


def _checked_body(
    request: HttpRequest, resource_type: str, identifier: str | None
) -> dict[str, object] | Failure:
    try:
        body = json.loads(request.body)
    except (ValueError, RecursionError):
        return Failure.invalid_input([BODY_PROBLEM])
    wrong = exact_elements(body, WRITE_SHAPES[resource_type], resource_type)
    if wrong is None and isinstance(body, dict):
        wrong = identity_problem(body, resource_type, identifier)
    if wrong is not None or not isinstance(body, dict):
        return Failure.invalid_input([FieldMessage(wrong or resource_type, "Not valid FHIR.")])
    return body


def _created(
    request: HttpRequest, resource_type: str, body: dict[str, object], caller: Caller
) -> HttpResponse:
    result = fhir_resources.create(resource_type, body, caller)
    if isinstance(result, Failure):
        return failure_response(result)
    response = resource_response(result.value, status=201)
    response["Location"] = request.build_absolute_uri(f"/fhir/{resource_type}/{result.value['id']}")
    return _with_etag(response, result.value)


def _deleted(
    resource_type: str, identifier: UUID, caller: Caller, version: int | None
) -> HttpResponse:
    result = fhir_resources.delete(resource_type, identifier, caller, version)
    if isinstance(result, Failure):
        return failure_response(result)
    outcome = information_outcome(DELETED_MESSAGE, current_request_context().correlation_id)
    return resource_response(outcome)


def _with_etag(response: HttpResponse, resource: Resource) -> HttpResponse:
    etag = weak_etag(resource)
    if etag is not None:
        response["ETag"] = etag
    return response
