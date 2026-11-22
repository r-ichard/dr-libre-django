"""Task 27d2, items 1, 4, 5, 6: a FHIR write says it is JSON, a reschedule changes only `start`,
`_sort` serves the date parameters, and a search value reads FHIR's escape for the comma."""

from datetime import timedelta

import pytest

from scheduling.models import Appointment
from scheduling.models.builders import STARTS_AT, make, make_clinic, make_user
from scheduling.views import clock
from scheduling.views.fhir_test_support import (
    FHIR_JSON,
    NOW,
    client_for,
    get,
    send,
    token_of,
)

pytestmark = pytest.mark.django_db

STAMP = "%Y-%m-%dT%H:%M:%SZ"
NEW_START = STARTS_AT + timedelta(days=14)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _booking_body(clinic: object) -> str:
    return (
        '{"resourceType": "Appointment", "status": "proposed", "start": "2030-01-07T10:00:00Z",'
        f' "serviceType": [{{"coding": [{{"code": "{clinic.appointment_type.pk}"}}]}}],'  # type: ignore[attr-defined]
        f' "participant": [{{"actor": {{"reference": "Patient/{clinic.patient.pk}"}},'  # type: ignore[attr-defined]
        ' "status": "accepted"}]}'
    )


@pytest.mark.parametrize(
    "media_type", ["text/plain", "application/xml", "text/plain; charset=utf-8"]
)
def returns_415_and_an_operation_outcome_when_a_fhir_write_says_a_type_that_is_not_json(
    media_type: str,
) -> None:
    clinic = make_clinic()
    token = token_of(clinic.patient)

    response = client_for(token).post(
        "/fhir/Appointment", data=_booking_body(clinic), content_type=media_type
    )

    assert (response.status_code, response.json()["resourceType"]) == (415, "OperationOutcome")
    assert Appointment.objects.count() == 0


@pytest.mark.parametrize(
    "media_type", [FHIR_JSON, "application/json", "application/JSON; charset=utf-8"]
)
def returns_201_when_a_fhir_write_says_json_in_either_spelling(media_type: str) -> None:
    clinic = make_clinic()
    token = token_of(clinic.patient)

    response = client_for(token).post(
        "/fhir/Appointment", data=_booking_body(clinic), content_type=media_type
    )

    assert response.status_code == 201


def returns_no_415_when_a_fhir_write_has_no_body_and_says_text_plain() -> None:
    token = token_of(role="ADMIN")

    response = client_for(token).generic(
        "DELETE", "/fhir/Schedule/00000000-0000-4000-8000-000000000000", CONTENT_TYPE="text/plain"
    )

    assert response.status_code != 415


@pytest.mark.parametrize(
    "path", ["/api/v1/auth/logout", "/fhir/Schedule/00000000-0000-4000-8000-000000000000"]
)
def returns_no_400_and_no_415_when_the_write_has_an_empty_content_length(path: str) -> None:
    token = token_of(role="ADMIN")

    response = client_for(token).generic(
        "DELETE" if path.startswith("/fhir") else "POST",
        path,
        CONTENT_TYPE="text/plain",
        CONTENT_LENGTH="",
    )

    assert response.status_code not in (400, 415)


def _booked(clinic: object, starts_at: object) -> Appointment:
    row = make(
        "Appointment",
        patient=clinic.patient,  # type: ignore[attr-defined]
        clinician=clinic.clinician,  # type: ignore[attr-defined]
        appointment_type=clinic.appointment_type,  # type: ignore[attr-defined]
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),  # type: ignore[operator]
    )
    assert isinstance(row, Appointment)
    return row


def _reschedule(end: str | None) -> tuple[int, dict[str, object], Appointment]:
    clinic = make_clinic()
    booked = _booked(clinic, STARTS_AT + timedelta(days=7))
    token = token_of(clinic.patient)
    body = get(f"/fhir/Appointment/{booked.pk}", token).json()
    body["start"] = NEW_START.strftime(STAMP)
    if end is None:
        body.pop("end", None)
    else:
        body["end"] = end
    response = send("put", f"/fhir/Appointment/{booked.pk}", body, token)
    booked.refresh_from_db()
    return response.status_code, response.json(), booked


def returns_200_and_the_moved_appointment_when_the_client_changes_only_start() -> None:
    status, _body, booked = _reschedule((STARTS_AT + timedelta(days=7, minutes=30)).strftime(STAMP))

    assert (status, booked.starts_at, booked.ends_at) == (
        200,
        NEW_START,
        NEW_START + timedelta(minutes=30),
    )


def returns_200_when_end_is_the_new_start_plus_the_duration() -> None:
    status, _body, _booked_row = _reschedule((NEW_START + timedelta(minutes=30)).strftime(STAMP))

    assert status == 200


def returns_400_naming_the_end_with_a_message_of_its_own_when_end_is_another_time() -> None:
    status, body, booked = _reschedule((NEW_START + timedelta(hours=5)).strftime(STAMP))

    issue = body["issue"][0]  # type: ignore[index]
    assert (status, issue["expression"], booked.starts_at == NEW_START) == (
        400,
        ["Appointment.end"],
        False,
    )
    assert "never taken from the client" in issue["diagnostics"]


def _times(count: int) -> list[str]:
    return [(STARTS_AT + timedelta(days=day)).strftime(STAMP) for day in range(count)]


def _sorted_starts(sort: str) -> list[str]:
    clinic = make_clinic()
    for day in (3, 1, 2):
        _booked(clinic, STARTS_AT + timedelta(days=day))
    response = get(f"/fhir/Appointment?_sort={sort}", token_of(role="ADMIN"))
    assert response.status_code == 200
    return [item["resource"]["start"] for item in response.json()["entry"]]


def returns_appointments_by_time_when_sort_is_date() -> None:
    assert _sorted_starts("date") == _times(4)[1:]


def returns_appointments_latest_first_when_sort_is_minus_date() -> None:
    assert _sorted_starts("-date") == _times(4)[1:][::-1]


def _birthdates(sort: str) -> list[str]:
    for year in (1990, 1970, 1980):
        make_user(role="PATIENT", date_of_birth=f"{year}-05-17")
    admin = token_of(role="ADMIN")
    response = get(f"/fhir/Patient?_sort={sort}", admin)
    assert response.status_code == 200
    return [
        item["resource"]["birthDate"]
        for item in response.json()["entry"]
        if "birthDate" in item["resource"]
    ]


def returns_patients_by_birth_date_when_sort_is_birthdate() -> None:
    assert _birthdates("birthdate") == ["1970-05-17", "1980-05-17", "1990-05-17"]


def returns_patients_youngest_first_when_sort_is_minus_birthdate() -> None:
    assert _birthdates("-birthdate") == ["1990-05-17", "1980-05-17", "1970-05-17"]


def returns_400_when_sort_names_a_parameter_that_does_not_exist() -> None:
    assert get("/fhir/Appointment?_sort=bogus", token_of(role="ADMIN")).status_code == 400


def returns_the_sort_values_of_each_type_in_its_documentation() -> None:
    capability = get("/fhir/metadata").json()
    appointment = next(
        item for item in capability["rest"][0]["resource"] if item["type"] == "Appointment"
    )

    assert "-date" in appointment["documentation"]


def returns_exactly_the_accepted_sort_values_in_each_types_documentation() -> None:
    capability = get("/fhir/metadata").json()
    documented = {item["type"]: item["documentation"] for item in capability["rest"][0]["resource"]}

    assert documented["Appointment"] == "`_sort` takes: date, -date."
    assert documented["Patient"] == "`_sort` takes: name, -name, birthdate, -birthdate."
    assert documented["CodeSystem"] == "`_sort` takes no value."


def returns_the_patient_named_smith_comma_john_when_the_comma_is_escaped() -> None:
    wanted = make_user(role="PATIENT", full_name="Smith, John")
    make_user(role="PATIENT", full_name="Smith")
    make_user(role="PATIENT", full_name="John")

    response = get("/fhir/Patient?name=Smith%5C%2C%20John", token_of(role="ADMIN"))

    assert [item["resource"]["id"] for item in response.json()["entry"]] == [str(wanted.pk)]
