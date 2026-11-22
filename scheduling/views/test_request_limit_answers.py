"""Task 17b, leftovers of 17a: a bad Content-Length header is a value in the contract, and a
page refused for its size answers in the product's layout with a correlation id."""

from __future__ import annotations

import pytest
from django.test import Client

from scheduling.views.pages.browser_support import SITE_ORIGIN

pytestmark = pytest.mark.django_db

ORIGIN = {"Origin": SITE_ORIGIN}
ONE_MEBIBYTE = 1024 * 1024
API_ROUTES = ["/api/v1/auth/login", "/api/v1/auth/link", "/api/v1/booking/holds"]


@pytest.mark.parametrize("path", API_ROUTES)
@pytest.mark.parametrize("length", ["abc", "-1", "1.5", " "])
def returns_400_invalid_input_naming_body_when_content_length_is_not_a_number(
    path: str, length: str
) -> None:
    client = Client(raise_request_exception=False)

    response = client.post(
        path, "{}", content_type="application/json", headers=ORIGIN, CONTENT_LENGTH=length
    )

    error = response.json()["error"]
    assert (response.status_code, error["code"]) == (400, "invalid_input")
    assert [item["field"] for item in error["details"]["fields"]] == ["body"]


def returns_400_page_with_layout_and_correlation_id_when_page_gets_201_fields(
    settings: object,
) -> None:
    settings.DEBUG = False  # type: ignore[attr-defined]
    query = "&".join(f"field{number}=1" for number in range(201))

    response = Client(raise_request_exception=False).get(
        f"/?{query}", headers={"X-Correlation-Id": "abc-400"}
    )

    html = response.content.decode()
    assert response.status_code == 400
    assert "abc-400" in html
    assert "<h1" in html and "<nav" in html


def returns_400_page_with_layout_and_correlation_id_when_page_body_is_over_1_mib(
    settings: object,
) -> None:
    settings.DEBUG = False  # type: ignore[attr-defined]
    body = "a=" + "x" * ONE_MEBIBYTE

    response = Client(raise_request_exception=False).post(
        "/sign-in",
        body,
        content_type="application/x-www-form-urlencoded",
        headers={"X-Correlation-Id": "abc-big", **ORIGIN},
    )

    html = response.content.decode()
    assert response.status_code == 400
    assert "abc-big" in html and "<h1" in html


def returns_400_page_in_the_layout_also_when_debug_is_on(settings: object) -> None:
    settings.DEBUG = True  # type: ignore[attr-defined]
    query = "&".join(f"field{number}=1" for number in range(201))

    response = Client(raise_request_exception=False).get(f"/?{query}")

    assert response.status_code == 400
    assert (
        "<h1" in response.content.decode() and "Bad Request (400)" not in response.content.decode()
    )


def returns_400_page_with_layout_when_host_is_not_allowed(settings: object) -> None:
    settings.DEBUG = False  # type: ignore[attr-defined]

    response = Client(raise_request_exception=False).get("/", headers={"Host": "evil.example"})

    html = response.content.decode()
    assert response.status_code == 400
    assert "<h1" in html and "<nav" in html
