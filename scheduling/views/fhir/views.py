"""Task 22, spec 15.1 and 15.4: the read-only /fhir door. One entry point routes by the
declaration; the view only parses the address, calls a use case and formats the answer."""

import logging

from django.http import HttpRequest, HttpResponse

from scheduling.domain.failure import Failure, FieldMessage
from scheduling.domain.fhir_bundle import search_bundle
from scheduling.domain.fhir_capability import capability_statement
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_declaration import FHIR_RESOURCES, declaration_for
from scheduling.domain.fhir_search import parse_id, parse_search
from scheduling.domain.request_limits import (
    MAXIMUM_BODY_BYTES,
    MAXIMUM_FIELDS,
    declared_length,
    query_field_count,
)
from scheduling.domain.vocabulary import Role
from scheduling.use_cases.api_tokens import resolve_token
from scheduling.use_cases.fhir_reads import Viewer, read_resource, search_resource
from scheduling.views.fhir.responses import (
    failure_response,
    internal_error_response,
    not_acceptable_response,
    resource_response,
)
from scheduling.views.network_address import network_address

logger = logging.getLogger("drlibre.fhir")

SERVED_MEDIA_TYPES = ("*/*", "application/*", "application/json", "application/fhir+json")
METADATA = "metadata"
BEARER_PREFIX = "Bearer "
STAFF_ROLES = (Role.CLINICIAN, Role.ADMIN)


def fhir_entry(request: HttpRequest) -> HttpResponse:
    try:
        return _answer(request, request.path.removeprefix("/fhir").strip("/"))
    except Exception:
        logger.exception("unexpected error")
        return internal_error_response()


def _answer(request: HttpRequest, rest: str) -> HttpResponse:
    refusal = _size_refusal(request)
    if refusal is not None:
        return failure_response(refusal)
    if not _accepts_fhir_json(request.headers.get("Accept", "")):
        return not_acceptable_response()
    viewer = _viewer(request)
    if isinstance(viewer, Failure):
        return failure_response(viewer)
    parts = rest.split("/") if rest else []
    if request.method != "GET" or not 1 <= len(parts) <= 2:
        return failure_response(Failure.not_found())
    if parts == [METADATA]:
        return resource_response(capability_statement(FHIR_RESOURCES))
    if declaration_for(parts[0]) is None:
        return failure_response(Failure.not_found())
    if len(parts) == 1:
        return _search(request, parts[0], viewer)
    return _read(parts[0], parts[1], viewer)


def _read(resource_type: str, raw_identifier: str, viewer: Viewer) -> HttpResponse:
    identifier = parse_id(raw_identifier) if raw_identifier != "specialty" else raw_identifier
    if identifier is None:
        return failure_response(Failure.not_found())
    result = read_resource(resource_type, identifier, viewer)
    if isinstance(result, Failure):
        return failure_response(result)
    response = resource_response(result.value)
    response["ETag"] = _weak_etag(result.value)
    return response


def _search(request: HttpRequest, resource_type: str, viewer: Viewer) -> HttpResponse:
    declaration = declaration_for(resource_type)
    if declaration is None:
        return failure_response(Failure.not_found())
    parsed = parse_search(declaration, dict(request.GET.lists()))
    if isinstance(parsed, Failure):
        return failure_response(parsed)
    found = search_resource(resource_type, parsed.value, viewer)
    if isinstance(found, Failure):
        return failure_response(found)
    bundle = search_bundle(
        service_base=request.build_absolute_uri("/fhir"),
        resource_type=resource_type,
        query=parsed.value,
        total=found.value.total,
        matches=found.value.matches,
        included=found.value.included,
    )
    return resource_response(bundle)


def _viewer(request: HttpRequest) -> Viewer | Failure:
    """No header is a public caller. Any header must be exactly `Bearer <token>`; anything else
    is presented as a token that cannot match, so it is 401 and counts as a failure. The cookie
    and the address are never read."""
    header = request.headers.get("Authorization")
    if header is None:
        return Viewer.PUBLIC
    token = header.removeprefix(BEARER_PREFIX) if header.startswith(BEARER_PREFIX) else header
    answer = resolve_token(token, network_address(request))
    if isinstance(answer, Failure):
        return answer
    return Viewer.STAFF if answer.value.role in STAFF_ROLES else Viewer.PUBLIC


def _size_refusal(request: HttpRequest) -> Failure | None:
    """The input limits of ADR 0004, checked before the query string is parsed."""
    if query_field_count(request.META.get("QUERY_STRING", "")) > MAXIMUM_FIELDS:
        return Failure.invalid_input([FieldMessage("query", "Too many fields.")])
    length = declared_length(request.META.get("CONTENT_LENGTH", ""))
    if length is None or length > MAXIMUM_BODY_BYTES:
        return Failure.invalid_input([FieldMessage("body", "The request body is not acceptable.")])
    return None


def _accepts_fhir_json(accept: str) -> bool:
    if not accept.strip():
        return True
    offered = (item.split(";", 1)[0].strip().lower() for item in accept.split(","))
    return any(media_type in SERVED_MEDIA_TYPES for media_type in offered)


def _weak_etag(resource: Resource) -> str:
    meta_block = resource.get("meta")
    version = meta_block.get("versionId", "") if isinstance(meta_block, dict) else ""
    return f'W/"{version}"'
