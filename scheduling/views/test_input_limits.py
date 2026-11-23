"""Section 4: an unexpected input is refused at the boundary, never a 500."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from scheduling.models.builders import make_clinic
from scheduling.views.api_clients import browser_api_client
from scheduling.views.pages.browser_support import SITE_ORIGIN
from scheduling.views.test_appointment_support import _signed_in

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

pytestmark = pytest.mark.django_db

SLOTS = "/api/v1/slots"
APPOINTMENTS = "/api/v1/appointments"
HOLDS = "/api/v1/booking/holds"
SEARCH = "/api/v1/search/hospitals"
JSON_TYPE = "application/json"
ORIGIN = {"Origin": SITE_ORIGIN}
DEEP = 100_000
THREE_MEGABYTES = 3 * 1024 * 1024
BODY_ROUTES = [HOLDS, "/api/v1/auth/link", "/api/v1/auth/login", APPOINTMENTS]


def _fields_named(response: Response) -> list[str]:
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    return [item["field"] for item in error["details"]["fields"]]


def _fields_named_or_empty(response: Response) -> list[str]:
    if response.status_code == 200:
        return []
    return _fields_named(response)


def _nested(depth: int) -> str:
    return "[" * depth + "]" * depth


@pytest.mark.parametrize("address", ["a@b", "not-an-email", "a@b@c"])
def returns_400_with_email_message_when_sign_in_page_gets_a_malformed_email(address: str) -> None:
    client = browser_api_client(raise_request_exception=False)

    response = client.post(
        "/sign-in", {"email": address, "password": "x"}, headers={"Origin": SITE_ORIGIN}
    )

    assert response.status_code == 400
    assert "Enter a valid email address." in response.content.decode()
    assert "drlibre_session" not in response.cookies


@pytest.mark.parametrize("instant", ["9999-12-31T23:59:59Z", "0001-01-01T00:00:00Z"])
def returns_400_invalid_input_naming_from_when_slots_ask_for_an_edge_date(instant: str) -> None:
    clinic = make_clinic()
    query = (
        f"appointment_type_id={clinic.appointment_type.pk}&from={instant}&to=2030-01-08T00:00:00Z"
    )

    response = browser_api_client(raise_request_exception=False).get(f"{SLOTS}?{query}")

    assert response.status_code == 400
    assert "from" in _fields_named(response)


@pytest.mark.parametrize("instant", ["9999-12-31T23:59:59Z", "0001-01-01T00:00:00Z"])
def returns_400_invalid_input_naming_starts_at_when_hold_asks_for_an_edge_date(
    instant: str,
) -> None:
    clinic = make_clinic()
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "starts_at": instant,
        "full_name": "Vera Visitor",
        "date_of_birth": "1985-03-14",
        "email": "vera.edge@example.test",
        "terms_accepted": True,
    }

    response = browser_api_client(raise_request_exception=False).post(
        HOLDS, json.dumps(body), content_type=JSON_TYPE, headers={"Origin": SITE_ORIGIN}
    )

    assert response.status_code == 400
    assert _fields_named(response) == ["starts_at"]


@pytest.mark.parametrize("page", ["99999999999999999999", "1000001"])
def returns_400_invalid_input_naming_page_when_page_is_huge(page: str) -> None:
    patient = make_clinic().patient
    client = _signed_in(patient)
    client.raise_request_exception = False

    response = client.get(f"{APPOINTMENTS}?page={page}")

    assert _fields_named(response) == ["page"]
    assert response.status_code == 400


@pytest.mark.parametrize("path", BODY_ROUTES)
def returns_400_invalid_input_naming_body_when_json_is_nested_100000_deep(path: str) -> None:
    client = _signed_in(make_clinic().patient)
    client.raise_request_exception = False

    response = client.post(
        path, _nested(DEEP), content_type=JSON_TYPE, headers={"Origin": SITE_ORIGIN}
    )

    assert response.status_code == 400
    assert _fields_named(response) == ["body"]


def returns_400_invalid_input_naming_body_when_body_is_3_megabytes() -> None:
    padding = json.dumps({"email": "x" * THREE_MEGABYTES})

    response = browser_api_client(raise_request_exception=False).post(
        "/api/v1/auth/link", padding, content_type=JSON_TYPE, headers={"Origin": SITE_ORIGIN}
    )

    assert response.status_code == 400
    assert _fields_named(response) == ["body"]


def returns_400_invalid_input_naming_query_when_search_has_1500_fields() -> None:
    query = "&".join(f"field{number}=1" for number in range(1500))

    response = browser_api_client(raise_request_exception=False).get(f"{SEARCH}?{query}")

    assert response.status_code == 400
    assert _fields_named(response) == ["query"]


def returns_400_not_500_when_json_is_nested_one_past_the_limit_and_200_class_at_it() -> None:
    at_limit, past_limit = _nested(20), _nested(21)
    client = browser_api_client(raise_request_exception=False)

    at_answer = client.post("/api/v1/auth/link", at_limit, content_type=JSON_TYPE, headers=ORIGIN)
    past_answer = client.post(
        "/api/v1/auth/link", past_limit, content_type=JSON_TYPE, headers=ORIGIN
    )

    assert _fields_named(at_answer) != ["body"]
    assert _fields_named(past_answer) == ["body"]


def _search_with(field_count: int) -> Response:
    query = "&".join(f"field{number}=1" for number in range(field_count))
    return browser_api_client(raise_request_exception=False).get(f"{SEARCH}?{query}")


def returns_400_for_201_query_fields_and_no_query_error_for_200() -> None:
    assert _fields_named(_search_with(201)) == ["query"]
    assert "query" not in _fields_named_or_empty(_search_with(200))


def _link_body_of(total_bytes: int) -> str:
    overhead = len(json.dumps({"email": ""}))
    return json.dumps({"email": "x" * (total_bytes - overhead)})


def returns_400_for_body_one_mebibyte_plus_one_and_no_body_error_at_one_mebibyte() -> None:
    mebibyte = 1024 * 1024
    client = browser_api_client(raise_request_exception=False)

    at_limit = client.post(
        "/api/v1/auth/link", _link_body_of(mebibyte), content_type=JSON_TYPE, headers=ORIGIN
    )
    past_limit = client.post(
        "/api/v1/auth/link", _link_body_of(mebibyte + 1), content_type=JSON_TYPE, headers=ORIGIN
    )

    assert "body" not in _fields_named(at_limit)
    assert _fields_named(past_limit) == ["body"]


def _depth_answer(raw: str, content_type: str = JSON_TYPE) -> Response:
    return browser_api_client(raise_request_exception=False).post(
        "/api/v1/auth/link", raw, content_type=content_type, headers={"Origin": SITE_ORIGIN}
    )


def returns_depth_error_only_for_brackets_outside_strings() -> None:
    brackets_in_string = json.dumps([":" + "[" * 30])
    escaped_quote_then_brackets = json.dumps(['"' + "[" * 30])
    escaped_backslash_then_real_nesting = '["\\\\", ' + _nested(25) + "]"

    assert "body" not in _fields_named(_depth_answer(brackets_in_string))
    assert "body" not in _fields_named(_depth_answer(escaped_quote_then_brackets))
    assert _fields_named(_depth_answer(escaped_backslash_then_real_nesting)) == ["body"]


def returns_no_depth_error_when_openers_are_many_but_depth_is_shallow() -> None:
    two_shallow_runs = "[" + _nested(15) + "," + _nested(15) + "]"

    assert "body" not in _fields_named(_depth_answer(two_shallow_runs))


def returns_unreadable_body_not_depth_error_when_body_is_not_json() -> None:
    answer = _depth_answer(_nested(30), content_type="text/plain")

    assert "nested too deeply" not in str(answer.json())
    assert "not readable" in str(answer.json())


def _appointments_from(instant: str) -> Response:
    client = _signed_in(make_clinic().patient)
    client.raise_request_exception = False
    return client.get(APPOINTMENTS, {"from": instant})


@pytest.mark.parametrize(
    "instant",
    [
        "1999-12-31T23:59:59Z",
        "2100-01-01T00:00:00Z",
        "0001-01-01T00:00:00+01:00",
        "9999-12-31T23:59:59-01:00",
    ],
)
def returns_400_naming_from_when_instant_is_outside_2000_to_2099(instant: str) -> None:
    response = _appointments_from(instant)

    assert response.status_code == 400
    assert _fields_named(response) == ["from"]


@pytest.mark.parametrize("instant", ["2000-01-01T00:00:00Z", "2099-12-31T23:59:59Z"])
def returns_200_when_instant_is_on_the_edge_of_2000_to_2099(instant: str) -> None:
    assert _appointments_from(instant).status_code == 200


def returns_400_when_a_page_posts_more_than_200_fields() -> None:
    form = {f"field{number}": "1" for number in range(250)} | {"email": "a@b.test", "password": "x"}

    response = browser_api_client(raise_request_exception=False).post(
        "/sign-in", form, headers={"Origin": SITE_ORIGIN}
    )

    assert response.status_code == 400
    assert "Email or password" not in response.content.decode()


def returns_400_when_a_page_posts_a_form_over_one_mebibyte() -> None:
    form = {"email": "a@b.test", "password": "x" * (1024 * 1024 + 1)}

    response = browser_api_client(raise_request_exception=False).post(
        "/sign-in", form, headers={"Origin": SITE_ORIGIN}
    )

    assert response.status_code == 400
    assert "Email or password" not in response.content.decode()
