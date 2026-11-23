import json
from datetime import UTC, datetime

import pytest
from django.test import Client

from scheduling.domain.failure import Failure
from scheduling.domain.request_context import RequestContext
from scheduling.use_cases.request_context import bind_request_context
from scheduling.views.api_clients import browser_api_client
from scheduling.views.failure_response import failure_response
from test_support.probe_views import SENSITIVE_MESSAGE

INSTANT = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("failure", "status"),
    [
        (Failure.invalid_input([]), 400),
        (Failure.unauthenticated(), 401),
        (Failure.forbidden(), 403),
        (Failure.not_found(), 404),
        (Failure.conflict(["room"]), 409),
        (Failure.no_room_available(), 409),
        (Failure.no_clinician_available(), 409),
        (Failure.invalid_transition("completed"), 409),
        (Failure.has_dependents(["appointments"]), 409),
        (Failure.rule_violation(["lead_time"]), 422),
    ],
)
def returns_status_of_the_table_when_each_of_ten_failures_is_mapped(
    failure: Failure, status: int
) -> None:
    with bind_request_context(RequestContext(correlation_id="cid-1", now=INSTANT)):
        response = failure_response(failure)

    assert response.status_code == status


def returns_error_body_with_code_message_correlation_id_and_details_when_failure_is_mapped() -> (
    None
):
    with bind_request_context(RequestContext(correlation_id="cid-1", now=INSTANT)):
        response = failure_response(Failure.invalid_transition("completed"))

    body = json.loads(response.rendered_content)
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "correlation_id", "details"}
    assert body["error"]["code"] == "invalid_transition"
    assert body["error"]["correlation_id"] == "cid-1"
    assert body["error"]["details"] == {"current_status": "completed"}
    assert isinstance(body["error"]["message"], str)
    assert "completed" not in body["error"]["message"]


def returns_resources_in_details_when_view_answers_conflict(probe_client: Client) -> None:
    response = probe_client.get("/api/v1/probe/conflict", headers={"x-correlation-id": "cid-2"})

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"resources": ["clinician", "room"]}


@pytest.mark.parametrize("debug", [True, False])
def returns_404_not_found_when_path_under_api_is_unknown(settings: object, debug: bool) -> None:
    settings.DEBUG = debug  # type: ignore[attr-defined]

    response = browser_api_client().get("/api/v1/nothing-here")

    assert response.status_code == 404
    error = response.json()["error"]
    assert (error["code"], error["details"]) == ("not_found", {})
    assert error["correlation_id"] == response["X-Correlation-Id"]


@pytest.mark.parametrize("method", ["post", "head", "options"])
def returns_404_not_found_when_method_is_not_allowed(method: str) -> None:
    response = getattr(browser_api_client(), method)("/api/v1/health")

    assert response.status_code == 404
    assert "Allow" not in response


def returns_400_invalid_input_naming_body_when_json_is_unreadable(probe_client: Client) -> None:
    response = probe_client.post(
        "/api/v1/probe/write", "{not json", content_type="application/json"
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert [item["field"] for item in error["details"]["fields"]] == ["body"]


def returns_400_invalid_input_with_field_messages_when_serializer_validation_fails(
    probe_client: Client,
) -> None:
    response = probe_client.post("/api/v1/probe/write", {}, content_type="application/json")

    assert response.status_code == 400
    assert response.json()["error"]["details"] == {
        "fields": [{"field": "start", "message": "This field is required."}]
    }


def returns_400_invalid_input_naming_each_unknown_field_when_write_has_extra_keys(
    probe_client: Client,
) -> None:
    payload = {"start": "2026-03-01T09:30:00Z", "role": "admin", "reason": "x"}

    response = probe_client.post("/api/v1/probe/write", payload, content_type="application/json")

    assert response.status_code == 400
    fields = response.json()["error"]["details"]["fields"]
    assert fields == [
        {"field": "reason", "message": "Unknown field."},
        {"field": "role", "message": "Unknown field."},
    ]


def returns_201_when_write_has_only_known_fields(probe_client: Client) -> None:
    payload = {"start": "2026-03-01T09:30:00Z"}

    response = probe_client.post("/api/v1/probe/write", payload, content_type="application/json")

    assert response.status_code == 201


@pytest.mark.parametrize("debug", [True, False])
def returns_500_internal_error_with_generic_message_and_correlation_id_when_view_raises(
    probe_client: Client, settings: object, debug: bool
) -> None:
    settings.DEBUG = debug  # type: ignore[attr-defined]

    response = probe_client.get("/api/v1/probe/explode", headers={"x-correlation-id": "cid-500"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Something went wrong.",
            "correlation_id": "cid-500",
            "details": {},
        }
    }
    text = response.content.decode()
    for leaked in ("Traceback", "ValueError", "probe_views", SENSITIVE_MESSAGE):
        assert leaked not in text


def returns_403_forbidden_when_view_declares_no_access_rule(probe_client: Client) -> None:
    response = probe_client.get("/api/v1/probe/undeclared")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def returns_200_when_health_declares_itself_public() -> None:
    response = browser_api_client().get("/api/v1/health")

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("django-denied", 403, "forbidden"),
        ("auth-failed", 401, "unauthenticated"),
        ("unsupported-media", 400, "invalid_input"),
    ],
)
def returns_table_status_and_code_with_generic_message_when_view_raises_framework_exception(
    probe_client: Client, path: str, status: int, code: str
) -> None:
    response = probe_client.get(f"/api/v1/probe/{path}")

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert SENSITIVE_MESSAGE not in response.content.decode()
