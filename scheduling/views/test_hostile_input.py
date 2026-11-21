"""Task 17a item 5: hostile values to every route found in the URL configuration; no 500."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Sequence

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver
from django.urls.converters import UUIDConverter
from hypothesis import given, settings, strategies

from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import SessionKind
from scheduling.models import User
from scheduling.models.builders import make
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
SESSION_COOKIE = "drlibre_session"
CATCH_ALL_SUFFIX = "x"  # the API catch-all is a prefix regex; a path under it exercises it
FIELD_NAMES = [
    "email", "password", "page", "page_size", "from", "to", "starts_at", "code", "q", "next",
    "appointment_type_id", "clinician_id", "token", "reason", "date", "week", "status",
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
    path = str(entry.pattern)
    for name, converter in entry.pattern.converters.items():
        if not isinstance(converter, UUIDConverter):
            raise AssertionError(f"route {path}: unknown converter {type(converter).__name__}")
        path = path.replace(f"<uuid:{name}>", str(uuid.uuid4()))
    return path


def _every_route_path() -> list[str]:
    paths = [
        "/" + path.lstrip("^").removesuffix("$")
        for path in _walk(get_resolver().url_patterns)
        if not path.startswith(SKIPPED_PREFIXES)
    ]
    return sorted({path + CATCH_ALL_SUFFIX if path.endswith("api/v1/") else path for path in paths})


def _hostile_requests() -> Iterator[tuple[str, dict[str, object]]]:
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


def _client_for(actor: str) -> Client:
    client = Client(raise_request_exception=False)
    if actor == "ANONYMOUS":
        return client
    user = make(
        "User",
        email=f"{actor.lower()}-{uuid.uuid4().hex}@example.test",
        role=actor,
        password=make_password("x"),
    )
    assert isinstance(user, User)
    with bind_request_context(RequestContext(correlation_id="hostile", now=clock.now_utc())):
        client.cookies[SESSION_COOKIE] = open_session(user, SessionKind.PASSWORD, "").token
    return client


@pytest.mark.parametrize("actor", ACTORS)
def returns_no_500_when_any_route_gets_hostile_input(actor: str) -> None:
    client = _client_for(actor)
    server_errors = [
        f"{actor} {method.upper()} {path} {kind} -> {status}"
        for path in _every_route_path()
        for kind, parts in _hostile_requests()
        for method in METHODS
        if (status := _send(client, method, path, kind, parts)) >= 500
    ]

    assert server_errors == []


JSON_VALUES = strategies.recursive(
    strategies.none() | strategies.booleans() | strategies.integers() | strategies.text(),
    lambda children: (
        strategies.lists(children) | strategies.dictionaries(strategies.text(), children)
    ),
    max_leaves=30,
)


@settings(max_examples=60, deadline=None)
@given(
    actor=strategies.sampled_from(ACTORS),
    path=strategies.sampled_from(_every_route_path()),
    method=strategies.sampled_from(METHODS),
    body=JSON_VALUES,
)
def returns_no_500_when_any_actor_sends_generated_json_to_any_route(
    actor: str, path: str, method: str, body: object
) -> None:
    client = _client_for(actor)
    parts: dict[str, object] = {"body": json.dumps(body)}

    assert _send(client, method, path, "json", parts) < 500
