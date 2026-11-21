"""Task 04b, section 16: security headers on every response, error responses included."""

import pytest
from django.http.response import HttpResponseBase
from django.test import Client

EXPECTED_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
    "connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; "
    "object-src 'none'"
)
FORBIDDEN_SOURCES = ("'unsafe-inline'", "'unsafe-eval'", "data:", "*")


def _assert_policy_headers(response: HttpResponseBase) -> None:
    assert response["Content-Security-Policy"] == EXPECTED_POLICY
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"


def returns_policy_headers_when_health_is_requested() -> None:
    response = Client().get("/api/v1/health")

    _assert_policy_headers(response)


@pytest.mark.parametrize("path", ["/api/v1/unmatched", "/pages/unmatched"])
def returns_policy_headers_when_route_is_unmatched(path: str) -> None:
    response = Client().get(path)

    assert response.status_code == 404
    _assert_policy_headers(response)


@pytest.mark.parametrize("path", ["/api/v1/probe/plain-explode", "/pages/explode"])
def returns_policy_headers_when_view_raises(probe_client: Client, path: str) -> None:
    response = probe_client.get(path)

    assert response.status_code == 500
    _assert_policy_headers(response)


def returns_no_inline_allowance_when_policy_is_parsed() -> None:
    policy = Client().get("/api/v1/health")["Content-Security-Policy"]

    sources = [source for directive in policy.split(";") for source in directive.split()[1:]]

    assert not set(sources) & set(FORBIDDEN_SOURCES)
