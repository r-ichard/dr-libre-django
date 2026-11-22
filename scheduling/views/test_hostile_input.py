"""Hostile values to every route of the URL configuration; no 500 (tasks 17a, 17b). Each path id
is a record the actor may use, so requests reach the parsing; a random id is one more case."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterator, Sequence
from functools import cache

import pytest
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver, resolve
from django.urls.converters import UUIDConverter
from hypothesis import given, settings, strategies

from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import SessionKind
from scheduling.models import User
from scheduling.models.builders import Clinic, make, make_clinic, make_user
from scheduling.use_cases.api_tokens import issue_token
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.session import open_session
from scheduling.views import clock
from scheduling.views.pages.browser_support import SITE_ORIGIN

pytestmark = pytest.mark.django_db

SKIPPED_PREFIXES = ("static/", "^static/")  # Django's file server, not product code
METHODS = ("get", "post", "put", "patch", "delete")
NESTED_DEEP = "[" * 100_000 + "]" * 100_000
HOSTILE_TEXT = ["", "x" * 100_000, "a\x00b", "NaN", str(10**30), "-1", "not-a-uuid"]
HOSTILE_DATES = ["0001-01-01", "9999-12-31T23:59:59Z", "2024-02-30", "0000-00-00T00:00:00Z"]
ACTORS = ("ANONYMOUS", "PATIENT", "CLINICIAN", "ADMIN")
SHARDS = 8
SESSION_COOKIE = "drlibre_session"
CATCH_ALL_SUFFIX = (
    "x"  # the API and FHIR catch-alls are prefix regexes; a path under it exercises it
)
FIELD_NAMES = [
    "email", "password", "page", "page_size", "from", "to", "starts_at", "code", "q", "next",
    "appointment_type_id", "clinician_id", "token", "reason", "date", "week", "status",
    "name", "version", "hospital", "department", "time_zone", "latitude", "longitude",
    "capacity", "colour", "equipment", "full_name", "role", "user", "specialty", "title", "bio",
    "default_room", "round_robin_weight", "user_id", "profile_id", "is_active",
]  # fmt: skip


def _walk(patterns: Sequence[URLPattern | URLResolver], prefix: str = "") -> Iterator[str]:
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _walk(entry.url_patterns, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            yield prefix + _path_of(entry)
        else:
            raise AssertionError(f"unknown url entry {entry!r}")


def _path_of(entry: URLPattern) -> str:
    """The route with its ids left as `<name>` markers, filled later per actor."""
    path = str(entry.pattern)
    for name, converter in entry.pattern.converters.items():
        if not isinstance(converter, UUIDConverter):
            raise AssertionError(f"route {path}: unknown converter {type(converter).__name__}")
        path = path.replace(f"<uuid:{name}>", f"<{name}>")
    return path


def _route_templates() -> list[str]:
    paths = [
        "/" + path.lstrip("^").removesuffix("$")
        for path in _walk(get_resolver().url_patterns)
        if not path.startswith(SKIPPED_PREFIXES)
    ]
    return sorted(
        {path + CATCH_ALL_SUFFIX if path.endswith(("api/v1/", "fhir/")) else path for path in paths}
    )


def _filled(template: str, ids: dict[str, str]) -> str:
    """Each `<name>` becomes the world's record of that name; with no world, a random id."""
    for name in re.findall(r"<(\w+)>", template):
        template = template.replace(f"<{name}>", ids[name] if ids else str(uuid.uuid4()))
    return template


def _every_route_path() -> list[str]:
    return sorted({_filled(template, {}) for template in _route_templates()})


def _record_of_every_kind() -> uuid.UUID:
    """The admin console routes share one `record_id` name, so one id names a record of each of
    the five kinds and every route of every kind reaches its parsing."""
    shared = uuid.uuid4()
    hospital = make("Hospital", id=shared)
    department = make("Department", id=shared, hospital=hospital)
    make("Specialty", id=shared)
    make("Room", id=shared, department=department)
    make("AppointmentType", id=shared, department=department)
    return shared


def _world_ids(clinic: Clinic) -> dict[str, str]:
    """One record of every kind a path names, tied to the clinic's patient and clinician."""
    appointment = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
    )
    return {
        "hospital_id": str(clinic.department.hospital_id),
        "provider_id": str(clinic.clinician.pk),
        "specialty_id": str(clinic.clinician.specialty_id),
        "appointment_type_id": str(clinic.appointment_type.pk),
        "appointment_id": str(appointment.pk),
        "hold_id": str(make("BookingHold", clinician=clinic.clinician).pk),
        "entry_id": str(
            make(
                "WaitlistEntry", patient=clinic.patient, appointment_type=clinic.appointment_type
            ).pk
        ),
        "notification_id": str(
            make("Notification", recipient=clinic.patient, appointment=appointment).pk
        ),
        "rule_id": str(make("AvailabilityRule", clinician=clinic.clinician, weekday=3).pk),
        "time_off_id": str(make("TimeOff", clinician=clinic.clinician).pk),
        "record_id": str(_record_of_every_kind()),
    }


def _actor_world(actor: str) -> tuple[Client, dict[str, str]]:
    """A fresh client signed in as the actor, and ids of records that actor may use."""
    clinic = make_clinic()
    client = Client(raise_request_exception=False)
    users = {
        "PATIENT": clinic.patient,
        "CLINICIAN": clinic.clinician.user,
        "ADMIN": make("User", role="ADMIN"),
    }
    user = users.get(actor)
    if user is not None:
        assert isinstance(user, User)
        with bind_request_context(RequestContext(correlation_id="hostile", now=clock.now_utc())):
            client.cookies[SESSION_COOKIE] = open_session(user, SessionKind.PASSWORD, "").token
    return client, _world_ids(clinic)


def _accepts(path: str, method: str) -> bool:
    """False when the route's view has no handler for the method: Django refuses that before any
    parsing, so only one request per method proves it."""
    view_class = getattr(resolve(path).func, "view_class", None)
    return view_class is None or (
        method in view_class.http_method_names and hasattr(view_class, method)
    )


@cache
def _hostile_requests() -> tuple[tuple[str, dict[str, object]], ...]:
    """Built once: the large bodies cost more to make than the request costs to send."""
    return tuple(_generate_hostile_requests())


def _generate_hostile_requests() -> Iterator[tuple[str, dict[str, object]]]:
    for value in HOSTILE_TEXT + HOSTILE_DATES:
        query = "&".join(f"{name}={value}" for name in FIELD_NAMES).replace("\x00", "%00")
        yield "query", {"query": query.encode("utf-8", "surrogatepass").decode("latin-1")}
        yield "json", {"body": json.dumps({name: value for name in FIELD_NAMES})}
        yield "form", {"body": {name: value for name in FIELD_NAMES}}
    wrong_types: list[object] = [[], 7, None, True, {"a": [1]}]
    for wrong_type in wrong_types:
        yield "json", {"body": json.dumps({name: wrong_type for name in FIELD_NAMES})}
    yield "json", {"body": NESTED_DEEP}
    yield "json", {"body": json.dumps({"email": "x" * (3 * 1024 * 1024)})}
    yield "json", {"body": b"\xff\xfe\x00{"}
    yield "query", {"query": "&".join(f"f{number}=1" for number in range(1500))}
    yield "form", {"body": {f"f{number}": "1" for number in range(1500)}}


PRE_GUARD_KINDS = 5  # the last requests of `_hostile_requests`: size and field counts


def _refused_by_guard(client: Client, method: str, path: str) -> bool:
    """True when the actor is turned away (401, 403, or a redirect to sign-in) before the route
    reads any value."""
    response = getattr(client, method)(path, headers={"Origin": SITE_ORIGIN})
    return response.status_code in (401, 403) or (
        response.status_code == 302 and response["Location"].startswith("/sign-in")
    )


def _requests_for(
    client: Client, path: str, method: str, known_record: bool
) -> Sequence[tuple[str, dict[str, object]]]:
    """Cut what proves nothing, never a route, actor or kind of value. A GET has no body: json
    and form are a plain GET. No handler, or an id naming no record: one request. A refused actor
    keeps the size and field-count requests, which are read before the guard."""
    every = _hostile_requests()
    if not known_record or not _accepts(path, method):
        return [every[-1] if method == "post" else every[1]]
    if _refused_by_guard(client, method, path):
        every = every[-PRE_GUARD_KINDS:]
    if method == "get":
        bare: tuple[str, dict[str, object]] = ("query", {"query": ""})
        return [bare] + [item for item in every if item[0] == "query"]
    return every


def _send(client: Client, method: str, path: str, kind: str, parts: dict[str, object]) -> int:
    headers = {"Origin": SITE_ORIGIN}
    if kind == "query":
        return int(getattr(client, method)(f"{path}?{parts['query']}", headers=headers).status_code)
    content_type = "application/json" if kind == "json" else "application/x-www-form-urlencoded"
    body = parts["body"]
    if kind == "form" and method != "post":
        body = "&".join(f"{key}={value}" for key, value in dict(body).items())  # type: ignore[call-overload]
    if method == "get":
        return int(client.get(path, headers=headers).status_code)
    sender = getattr(client, method)
    if kind == "form" and method == "post":
        return int(sender(path, body, headers=headers).status_code)
    return int(sender(path, body, content_type=content_type, headers=headers).status_code)


def returns_a_route_list_that_includes_pages_and_api_routes() -> None:
    paths = _every_route_path()

    assert "/sign-in" in paths
    assert "/api/v1/slots" in paths
    assert len(paths) > 50


def returns_one_world_id_for_every_name_a_path_uses() -> None:
    names = {name for template in _route_templates() for name in re.findall(r"<(\w+)>", template)}
    _, ids = _actor_world("ANONYMOUS")

    assert names <= set(ids)


def returns_422_from_its_own_parser_when_own_appointment_gets_a_hostile_reason() -> None:
    client, ids = _actor_world("PATIENT")
    path = f"/patient/appointments/{ids['appointment_id']}/cancel"

    status = _send(client, "post", path, "form", {"body": {"reason": "x" * 100_000}})

    assert status == 422


def _server_errors(actor: str, template: str) -> list[str]:
    """A fresh world per route: an earlier request may cancel or delete what a later one names."""
    client, ids = _actor_world(actor)
    cases = [(_filled(template, ids), True)]
    if ids and "<" in template:
        cases.append((_filled(template, {}), False))
    return [
        f"{actor} {method.upper()} {path} {kind} -> {status}"
        for path, known_record in cases
        for method in METHODS
        for kind, parts in _requests_for(client, path, method, known_record)
        if (status := _send(client, method, path, kind, parts)) >= 500
    ]


@pytest.mark.parametrize("shard", range(SHARDS))
@pytest.mark.parametrize("actor", ACTORS)
def returns_no_500_when_any_route_gets_hostile_input(actor: str, shard: int) -> None:
    templates = _route_templates()[shard::SHARDS]

    server_errors = [error for template in templates for error in _server_errors(actor, template)]

    assert server_errors == []


JSON_VALUES = strategies.recursive(
    strategies.none() | strategies.booleans() | strategies.integers() | strategies.text(),
    lambda children: (
        strategies.lists(children) | strategies.dictionaries(strategies.text(), children)
    ),
    max_leaves=30,
)


@pytest.mark.parametrize("actor", ACTORS)
def returns_no_500_when_actor_sends_generated_json_to_any_route(actor: str) -> None:
    client, ids = _actor_world(actor)
    paths = sorted({_filled(template, ids) for template in _route_templates()})

    @settings(max_examples=60, deadline=None)
    @given(
        path=strategies.sampled_from(paths),
        method=strategies.sampled_from(METHODS),
        body=JSON_VALUES,
    )
    def attempt(path: str, method: str, body: object) -> None:
        assert _send(client, method, path, "json", {"body": json.dumps(body)}) < 500

    attempt()


FHIR_TYPES = ["Organization", "Location", "HealthcareService", "CodeSystem", "ValueSet",
              "Practitioner", "PractitionerRole", "metadata", "Nothing"]  # fmt: skip
FHIR_AUTHORIZATIONS = [
    "", "Bearer", "Bearer ", "Basic abc", "Bearer \x00", "Bearer " + "x" * 100_000, "bearer x",
    "Bearer dlk_unknown", "Bearer " + "é" * 50,
]  # fmt: skip


@pytest.mark.parametrize("actor", ["ANONYMOUS", "ADMIN", "CLINICIAN", "PATIENT"])
def returns_outcome_and_no_500_when_fhir_gets_hostile_authorization(actor: str) -> None:
    clinic = make_clinic()
    headers_to_try = [{"Authorization": value} for value in FHIR_AUTHORIZATIONS]
    if actor != "ANONYMOUS":
        with bind_request_context(RequestContext("hostile", clock.now_utc())):
            token = issue_token(make_user(role=actor), "Hostile").token
        headers_to_try.append({"Authorization": f"Bearer {token}"})
    client = Client(raise_request_exception=False)
    paths = [f"/fhir/{name}" for name in FHIR_TYPES] + [
        f"/fhir/Organization/{clinic.department.hospital_id}",
        f"/fhir/Practitioner/{clinic.clinician.user_id}",
        "/fhir/Practitioner/not-an-id",
    ]

    failures = []
    for headers in headers_to_try:
        for path in paths:
            for query in ("", "?_count=x&name=%00&_include=%00&near=%00"):
                response = client.get(path + query, headers=headers)
                body = response.json()
                if response.status_code >= 500 or (
                    response.status_code >= 400 and body["resourceType"] != "OperationOutcome"
                ):
                    failures.append((path, query, response.status_code))
    assert failures == []
