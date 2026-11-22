"""Test clients for API routes. Both enforce the cross-site check, which Django's default test
client skips. A browser sends `Origin` and keeps cookies; a FHIR client sends a bearer token and
neither (ADR 0005)."""

from django.test import Client

SITE_ORIGIN = "http://testserver"
CSRF_VALUE = "c" * 32  # a browser that loaded a page holds this cookie and echoes it in a header


def browser_api_client(*, raise_request_exception: bool = True) -> Client:
    client = Client(
        enforce_csrf_checks=True,
        raise_request_exception=raise_request_exception,
        headers={"Origin": SITE_ORIGIN, "X-CSRFToken": CSRF_VALUE},
    )
    client.cookies["csrftoken"] = CSRF_VALUE
    return client


def fhir_client(token: str | None = None) -> Client:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return Client(enforce_csrf_checks=True, raise_request_exception=False, headers=headers)
