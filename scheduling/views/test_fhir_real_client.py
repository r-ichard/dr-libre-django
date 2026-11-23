"""Sections 15.1, 15.4: /fhir is a bearer-token door for a server client. The client sends
a token, no cookie and no Origin; the cross-site check is enforced, as in a browser."""

from typing import TYPE_CHECKING

import pytest
from django.test import Client

from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import SessionKind
from scheduling.models.builders import make, make_user
from scheduling.use_cases.api_tokens import issue_token
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.session import open_session
from scheduling.views import clock
from scheduling.views.pages.search_pages_support import plant_clinic, update_row

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

FHIR_JSON = "application/fhir+json"
WRITE_METHODS = ("post", "put", "patch", "delete")


def _server_client() -> Client:
    return Client(enforce_csrf_checks=True, raise_request_exception=False)


def _token(role: str = "ADMIN") -> str:
    with bind_request_context(RequestContext("test-token", clock.now_utc())):
        return issue_token(make_user(role=role), "Reporting").token


def _get(path: str, token: str | None = None) -> "_MonkeyPatchedWSGIResponse":
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return _server_client().get(path, headers=headers)


@pytest.mark.parametrize("method", WRITE_METHODS)
def returns_405_with_allow_get_and_outcome_when_write_sent_to_known_type(method: str) -> None:
    client = _server_client()

    for path in ("/fhir/ValueSet", "/fhir/ValueSet/specialty", "/fhir/metadata"):
        response = getattr(client, method)(path, headers={"Authorization": f"Bearer {_token()}"})

        assert response.status_code == 405
        assert response["Content-Type"].startswith(FHIR_JSON)
        assert response["Allow"] == "GET"
        assert response.json()["resourceType"] == "OperationOutcome"


@pytest.mark.parametrize("method", WRITE_METHODS)
def returns_404_json_when_write_sent_to_unknown_type(method: str) -> None:
    response = getattr(_server_client(), method)("/fhir/Nothing", headers={})

    assert response.status_code == 404
    assert response["Content-Type"].startswith(FHIR_JSON)


def returns_401_json_when_write_sent_with_bad_token() -> None:
    response = _server_client().post("/fhir/Organization", headers={"Authorization": "Bearer x"})

    assert response.status_code == 401
    assert response["Content-Type"].startswith(FHIR_JSON)


def returns_json_405_and_public_view_when_foreign_origin_and_admin_cookie_sent() -> None:
    clinician, appointment_type = plant_clinic()
    update_row(appointment_type, is_bookable_online=False)
    client = _server_client()
    with bind_request_context(RequestContext("test-cookie", clock.now_utc())):
        client.cookies["drlibre_session"] = open_session(
            make_user(role="ADMIN"), SessionKind.PASSWORD, ""
        ).token

    write = client.post("/fhir/Practitioner", headers={"Origin": "https://evil.example"})
    read = client.get(f"/fhir/Practitioner/{clinician.user_id}")

    assert (write.status_code, write["Content-Type"].startswith(FHIR_JSON)) == (405, True)
    assert read.status_code == 404


def returns_vary_authorization_on_every_answer() -> None:
    plant_clinic()
    token = _token()
    answers = [
        _get("/fhir/Organization"),
        _get("/fhir/Organization", token),
        _get("/fhir/Organization?nope=1"),
        _get("/fhir/Organization", "bad"),
        _get("/fhir/Nothing"),
        _server_client().post("/fhir/Practitioner"),
        _server_client().get("/fhir/Organization", headers={"Accept": "text/html"}),
    ]

    assert [answer.status_code for answer in answers] == [200, 200, 400, 401, 404, 405, 406]
    assert all("Authorization" in answer["Vary"] for answer in answers)


def returns_no_store_when_token_sent_and_not_when_public() -> None:
    plant_clinic()

    with_token = _get("/fhir/Organization", _token())
    refused = _get("/fhir/Organization", "bad")
    public = _get("/fhir/Organization")

    assert with_token["Cache-Control"] == "no-store"
    assert refused["Cache-Control"] == "no-store"
    assert "no-store" not in public.get("Cache-Control", "")


def returns_both_included_kinds_when_include_repeated() -> None:
    plant_clinic()
    path = (
        "/fhir/PractitionerRole?_include=PractitionerRole:practitioner"
        "&_include=PractitionerRole:organization"
    )

    response = _get(path)

    assert response.status_code == 200
    kinds = {entry["resource"]["resourceType"] for entry in response.json()["entry"]}
    assert kinds == {"PractitionerRole", "Practitioner", "Organization"}


def returns_all_services_to_staff_and_only_bookable_to_public_when_a_service_is_not_bookable() -> (
    None
):
    clinician, hidden_type = plant_clinic()
    update_row(hidden_type, is_bookable_online=False)
    visible_type = make("AppointmentType", department=clinician.department, name="Follow-up")
    path = f"/fhir/PractitionerRole/{clinician.pk}"

    staff = _get(path, _token()).json()["healthcareService"]
    public = _get(path).json()["healthcareService"]

    assert {item["reference"] for item in staff} == {
        f"HealthcareService/{hidden_type.pk}",
        f"HealthcareService/{visible_type.pk}",
    }
    assert public == [{"reference": f"HealthcareService/{visible_type.pk}"}]


def returns_contact_only_to_staff_when_practitioner_included_in_role_search() -> None:
    plant_clinic()
    path = "/fhir/PractitionerRole?_include=PractitionerRole:practitioner"

    def practitioner(token: str | None) -> dict[str, object]:
        entries = _get(path, token).json()["entry"]
        resources = [entry["resource"] for entry in entries]
        return next(item for item in resources if item["resourceType"] == "Practitioner")

    assert "telecom" in practitioner(_token())
    assert "telecom" not in practitioner(None)


def returns_200_for_valid_token_when_twenty_bad_tokens_came_from_its_address() -> None:
    plant_clinic()
    token = _token()
    for attempt in range(20):
        _get("/fhir/Organization", f"bad-{attempt}")

    assert _get("/fhir/Organization", token).status_code == 200
    assert _get("/fhir/Organization", "bad-again").status_code == 429


def returns_401_then_429_after_five_bad_tries_of_one_token() -> None:
    codes = [_get("/fhir/Organization", "same-bad").status_code for _ in range(7)]

    assert codes == [401] * 5 + [429] * 2
