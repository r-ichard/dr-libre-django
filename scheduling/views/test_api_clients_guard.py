"""Task 22a: a test of an API route gets a client that enforces the cross-site check from
`scheduling/views/api_clients.py`; none builds `Client(` itself. `pages/` keeps its own."""

import ast
from pathlib import Path

import pytest

from scheduling.views.api_clients import CSRF_VALUE, SITE_ORIGIN, browser_api_client, fhir_client

VIEWS = Path(__file__).parent


def _builds_client(path: Path) -> bool:
    return any(
        isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Client"
        for node in ast.walk(ast.parse(path.read_text()))
    )


def returns_no_offender_when_test_modules_use_the_api_client_helpers() -> None:
    modules = [
        path
        for path in sorted(VIEWS.glob("test_*.py"))
        if path.name not in {Path(__file__).name, "test_fhir_real_client.py"}
    ]

    offenders = [path.name for path in modules if _builds_client(path)]

    assert offenders == []
    assert (VIEWS / "api_clients.py").exists()


HOLDS = "/api/v1/booking/holds"


@pytest.mark.django_db
def returns_403_when_browser_client_posts_from_a_foreign_origin() -> None:
    foreign = {"Origin": "http://evil.example"}

    client = browser_api_client()

    response = client.post(HOLDS, {}, content_type="application/json", headers=foreign)

    assert response.status_code == 403


def returns_origin_cookie_and_token_when_browser_client_built() -> None:
    client = browser_api_client()

    assert client.handler.enforce_csrf_checks
    assert client.cookies["csrftoken"].value == CSRF_VALUE
    assert client.defaults["HTTP_ORIGIN"] == SITE_ORIGIN
    assert client.defaults["HTTP_X_CSRFTOKEN"] == CSRF_VALUE


def returns_no_cookie_and_no_origin_when_fhir_client_built() -> None:
    client = fhir_client("secret")

    assert client.handler.enforce_csrf_checks
    assert not client.cookies
    assert "HTTP_ORIGIN" not in client.defaults
    assert client.defaults["HTTP_AUTHORIZATION"] == "Bearer secret"
