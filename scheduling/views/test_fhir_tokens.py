"""Task 22, spec 15.4: a bearer token gives exactly its user's rights under /fhir; a bad one is
401 and never the answer of no token; the session cookie and the address never authenticate."""

import logging
from typing import TYPE_CHECKING

import pytest

from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import SessionKind
from scheduling.models.builders import make_user
from scheduling.use_cases.api_tokens import issue_token, revoke_token
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.session import open_session
from scheduling.views import clock
from scheduling.views.api_clients import fhir_client
from scheduling.views.pages.search_pages_support import (
    PLANTED_BIRTH,
    PLANTED_EMAIL,
    PLANTED_PHONE,
    plant_clinic,
    update_row,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db


def _token_for(role: str) -> str:
    user = make_user(role=role)
    with bind_request_context(RequestContext("test-token", clock.now_utc())):
        return issue_token(user, "Reporting").token


def _get(path: str, token: str | None = None) -> "_MonkeyPatchedWSGIResponse":
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return fhir_client().get(path, headers=headers)


def _ids(path: str, token: str | None = None) -> list[str]:
    return [entry["resource"]["id"] for entry in _get(path, token).json().get("entry", [])]


@pytest.mark.parametrize("role", ["CLINICIAN", "ADMIN"])
def returns_inactive_hospital_and_hidden_clinician_when_staff_token_presented(role: str) -> None:
    clinician, appointment_type = plant_clinic()
    hospital = clinician.department.hospital
    update_row(hospital, is_active=False)
    update_row(appointment_type, is_bookable_online=False)
    token = _token_for(role)

    assert _get(f"/fhir/Organization/{hospital.pk}").status_code == 404
    assert _get(f"/fhir/Organization/{hospital.pk}", token).json()["active"] is False
    assert _get(f"/fhir/Location/{hospital.pk}", token).status_code == 200
    assert _get(f"/fhir/Practitioner/{clinician.user_id}", token).status_code == 200
    assert _get(f"/fhir/PractitionerRole/{clinician.pk}", token).status_code == 200
    assert _get(f"/fhir/HealthcareService/{appointment_type.pk}", token).status_code == 200
    assert str(hospital.pk) in _ids("/fhir/Organization", token)
    assert str(clinician.user_id) in _ids("/fhir/Practitioner", token)
    assert _ids("/fhir/Practitioner") == []


def returns_email_and_phone_but_no_birth_date_when_staff_token_reads_practitioner() -> None:
    clinician, _ = plant_clinic()

    text = _get(f"/fhir/Practitioner/{clinician.user_id}", _token_for("CLINICIAN")).content.decode()

    assert PLANTED_EMAIL in text
    assert PLANTED_PHONE in text
    assert PLANTED_BIRTH not in text


def returns_inactive_clinician_in_search_when_staff_token_presented() -> None:
    clinician, _ = plant_clinic()
    update_row(clinician.user, is_active=False)

    assert _ids("/fhir/Practitioner") == []
    assert _ids("/fhir/Practitioner", _token_for("ADMIN")) == [str(clinician.user_id)]


def returns_public_answer_when_patient_token_presented() -> None:
    clinician, appointment_type = plant_clinic()
    update_row(appointment_type, is_bookable_online=False)
    token = _token_for("PATIENT")

    response = _get(f"/fhir/Practitioner/{clinician.user_id}", token)

    assert response.status_code == 404
    assert _ids("/fhir/Practitioner", token) == []
    update_row(appointment_type, is_bookable_online=True)
    assert (
        PLANTED_EMAIL not in _get(f"/fhir/Practitioner/{clinician.user_id}", token).content.decode()
    )


def returns_401_outcome_when_token_unknown_revoked_or_user_inactive() -> None:
    plant_clinic()
    revoked_user = make_user(role="ADMIN")
    inactive_user = make_user(role="ADMIN")
    with bind_request_context(RequestContext("test-token", clock.now_utc())):
        revoked = issue_token(revoked_user, "One")
        inactive = issue_token(inactive_user, "Two")
        revoke_token(revoked.client.pk)
    update_row(inactive_user, is_active=False)

    for token in ("dlk_unknown", revoked.token, inactive.token):
        response = _get("/fhir/Organization", token)
        assert response.status_code == 401
        assert response.json()["resourceType"] == "OperationOutcome"
        assert token not in response.content.decode()
        assert response["X-Correlation-Id"]


@pytest.mark.parametrize(
    "header", ["Basic abc", "Bearer", "Bearer  dlk_x", "bearer dlk_x", "x" * 5000]
)
def returns_401_outcome_when_authorization_header_is_malformed(header: str) -> None:
    plant_clinic()

    response = fhir_client().get("/fhir/Organization", headers={"Authorization": header})

    assert response.status_code == 401
    assert response.json()["resourceType"] == "OperationOutcome"


def returns_401_when_token_unknown_on_metadata() -> None:
    assert _get("/fhir/metadata", "dlk_unknown").status_code == 401


def returns_public_answer_when_session_cookie_is_the_only_credential() -> None:
    clinician, appointment_type = plant_clinic()
    update_row(appointment_type, is_bookable_online=False)
    admin = make_user(role="ADMIN")
    client = fhir_client()
    with bind_request_context(RequestContext("test-cookie", clock.now_utc())):
        client.cookies["drlibre_session"] = open_session(admin, SessionKind.PASSWORD, "").token

    response = client.get(f"/fhir/Practitioner/{clinician.user_id}")

    assert response.status_code == 404


def returns_refusal_and_no_staff_answer_when_token_is_in_the_address() -> None:
    clinician, appointment_type = plant_clinic()
    update_row(appointment_type, is_bookable_online=False)
    token = _token_for("ADMIN")

    response = _get(f"/fhir/Practitioner/{clinician.user_id}?access_token={token}")

    assert response.status_code == 404
    assert _ids(f"/fhir/Practitioner?access_token={token}") == []
    assert _get(f"/fhir/Practitioner?access_token={token}").status_code == 400


def returns_429_outcome_when_one_token_failed_more_than_five_times(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        statuses = [_get("/fhir/Organization", "dlk_wrong").status_code for _ in range(7)]

    assert statuses == [401] * 5 + [429] * 2
    assert "dlk_wrong" not in caplog.text
