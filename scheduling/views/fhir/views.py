"""Task 22 and 23, spec 15.1 and 15.4: the /fhir door. One entry point routes by the declaration;
the view only parses the address, calls a use case and formats the answer."""

import logging

from django.http import HttpRequest, HttpResponse
from django.utils.cache import patch_vary_headers
from django.views.decorators.csrf import csrf_exempt

from scheduling.domain.failure import Failure, FieldMessage
from scheduling.domain.fhir_bundle import search_bundle
from scheduling.domain.fhir_capability import capability_statement
from scheduling.domain.fhir_declaration import FHIR_RESOURCES, ResourceDeclaration, declaration_for
from scheduling.domain.fhir_search import parse_id, parse_search
from scheduling.domain.request_limits import (
    MAXIMUM_BODY_BYTES,
    MAXIMUM_FIELDS,
    declared_length,
    query_field_count,
)
from scheduling.domain.vocabulary import Role
from scheduling.use_cases import fhir_resources
from scheduling.use_cases.api_tokens import resolve_token
from scheduling.use_cases.fhir_caller import PUBLIC_CALLER, Caller
from scheduling.use_cases.fhir_reads import Viewer
from scheduling.views.fhir.responses import (
    failure_response,
    internal_error_response,
    method_not_allowed_response,
    not_acceptable_response,
    resource_response,
    weak_etag,
)
from scheduling.views.fhir.writes import write
from scheduling.views.network_address import network_address

logger = logging.getLogger("drlibre.fhir")

SERVED_MEDIA_TYPES = ("*/*", "application/*", "application/json", "application/fhir+json")
METADATA = "metadata"
BEARER_PREFIX = "Bearer "
STAFF_ROLES = (Role.CLINICIAN, Role.ADMIN)
NO_STORE_TYPES = ("Patient", "Appointment", "AppointmentResponse", "Communication", "AuditEvent")
METHOD_OF_INTERACTION = {
    "read": "GET",
    "search-type": "GET",
    "create": "POST",
    "update": "PUT",
    "delete": "DELETE",
}


@csrf_exempt
def fhir_entry(request: HttpRequest) -> HttpResponse:
    """Exempt from the cross-site check: a FHIR client sends a bearer token and no cookie, and
    this door never reads a cookie, so the check has nothing to protect (ADR 0005)."""
    try:
        response = _answer(request, request.path.removeprefix("/fhir").strip("/"))
    except Exception:
        logger.exception("unexpected error")
        response = internal_error_response()
    patch_vary_headers(response, ("Authorization",))
    first_part = request.path.removeprefix("/fhir").strip("/").split("/")[0]
    if "Authorization" in request.headers or first_part in NO_STORE_TYPES:
        response["Cache-Control"] = "no-store"
    return response


def _answer(request: HttpRequest, rest: str) -> HttpResponse:
    refusal = _size_refusal(request)
    if refusal is not None:
        return failure_response(refusal)
    if not _accepts_fhir_json(request.headers.get("Accept", "")):
        return not_acceptable_response()
    caller = _caller(request)
    if isinstance(caller, Failure):
        return failure_response(caller)
    parts = rest.split("/") if rest else []
    known = parts == [METADATA] or (1 <= len(parts) <= 2 and declaration_for(parts[0]) is not None)
    if not known:
        return failure_response(Failure.not_found())
    allowed = _allowed_methods(parts)
    if request.method not in allowed:
        return method_not_allowed_response(allowed)
    if parts == [METADATA]:
        return resource_response(capability_statement(FHIR_RESOURCES))
    if request.method != "GET":
        return write(request, parts[0], parts[1] if len(parts) == 2 else None, caller)
    if len(parts) == 1:
        return _search(request, parts[0], caller)
    return _read(parts[0], parts[1], caller)


def _allowed_methods(parts: list[str]) -> tuple[str, ...]:
    if parts == [METADATA]:
        return ("GET",)
    declaration = declaration_for(parts[0])
    if declaration is None:
        return ()
    return _methods_of(declaration, instance=len(parts) == 2)


def _methods_of(declaration: ResourceDeclaration, *, instance: bool) -> tuple[str, ...]:
    shape_interactions = ("read", "update", "delete") if instance else ("search-type", "create")
    methods = [
        METHOD_OF_INTERACTION[item]
        for item in shape_interactions
        if item in declaration.interactions
    ]
    return tuple(dict.fromkeys(methods))


def _read(resource_type: str, raw_identifier: str, caller: Caller) -> HttpResponse:
    identifier = parse_id(raw_identifier) if raw_identifier != "specialty" else raw_identifier
    if identifier is None and resource_type == "Slot":
        identifier = raw_identifier
    if identifier is None:
        return failure_response(Failure.not_found())
    result = fhir_resources.read(resource_type, identifier, caller)
    if isinstance(result, Failure):
        return failure_response(result)
    response = resource_response(result.value)
    etag = weak_etag(result.value)
    if etag is not None:
        response["ETag"] = etag
    return response


def _search(request: HttpRequest, resource_type: str, caller: Caller) -> HttpResponse:
    declaration = declaration_for(resource_type)
    if declaration is None:
        return failure_response(Failure.not_found())
    parsed = parse_search(declaration, dict(request.GET.lists()))
    if isinstance(parsed, Failure):
        return failure_response(parsed)
    found = fhir_resources.search(resource_type, parsed.value, caller)
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


def _caller(request: HttpRequest) -> Caller | Failure:
    """No header is a public caller. Any header must be exactly `Bearer <token>`; anything else
    is presented as a token that cannot match, so it is 401 and counts as a failure. The cookie
    and the address are never read."""
    header = request.headers.get("Authorization")
    if header is None:
        return PUBLIC_CALLER
    token = header.removeprefix(BEARER_PREFIX) if header.startswith(BEARER_PREFIX) else header
    answer = resolve_token(token, network_address(request))
    if isinstance(answer, Failure):
        return answer
    user = answer.value
    return Caller(Viewer.STAFF if user.role in STAFF_ROLES else Viewer.PUBLIC, user)


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
