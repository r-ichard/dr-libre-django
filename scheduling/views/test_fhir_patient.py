"""Task 23, spec 12.3, 15.4, 15.5: Patient is personal data. Each caller reads only what the role
allows, an answer never tells whether another patient exists, every answer is no-store, and no
record value reaches a log."""

import logging
from datetime import date

import pytest

from scheduling.models import AuditLogEntry, User
from scheduling.models.builders import make, make_clinic, make_user
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, get, send, token_of

pytestmark = pytest.mark.django_db

PLANTED_PHONE = "+49 777 313373"
PLANTED_EMAIL = "planted.log.patient@example.org"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _patient(**fields: object) -> User:
    return make_user(role="PATIENT", **fields)


def returns_own_record_with_birth_date_and_no_store_when_patient_reads_self() -> None:
    patient = _patient(date_of_birth=date(1985, 5, 17), phone="+49 30 1234")

    response = get(f"/fhir/Patient/{patient.pk}", token_of(patient))

    body = response.json()
    assert response.status_code == 200
    assert body["birthDate"] == "1985-05-17"
    assert {"system": "phone", "value": "+49 30 1234"} in body["telecom"]
    assert response["Cache-Control"] == "no-store"


def returns_401_when_patient_is_read_without_token() -> None:
    patient = _patient()

    assert get(f"/fhir/Patient/{patient.pk}").status_code == 401
    assert get("/fhir/Patient").status_code == 401


@pytest.mark.parametrize("role", ["PATIENT", "CLINICIAN"])
def returns_same_403_for_another_patient_as_for_an_absent_id(role: str) -> None:
    clinic = make_clinic()
    other = _patient()
    caller = clinic.clinician.user if role == "CLINICIAN" else _patient()
    token = token_of(caller)
    absent = "00000000-0000-4000-8000-000000000000"

    foreign = get(f"/fhir/Patient/{other.pk}", token)
    missing = get(f"/fhir/Patient/{absent}", token)

    assert foreign.status_code == missing.status_code == 403
    assert foreign.json()["issue"][0]["details"] == missing.json()["issue"][0]["details"]
    assert foreign["Cache-Control"] == missing["Cache-Control"] == "no-store"


def returns_404_when_admin_reads_an_absent_patient() -> None:
    absent = "00000000-0000-4000-8000-000000000000"

    assert get(f"/fhir/Patient/{absent}", token_of(role="ADMIN")).status_code == 404


def returns_only_patients_with_an_appointment_when_clinician_searches() -> None:
    clinic = make_clinic()
    seen = _patient(full_name="Seen Patient")
    make(
        "Appointment",
        patient=seen,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
    )
    _patient(full_name="Stranger Patient")

    response = get("/fhir/Patient", token_of(clinic.clinician.user))

    assert response.json()["total"] == 1
    assert [e["resource"]["id"] for e in response.json()["entry"]] == [str(seen.pk)]


def returns_total_of_readable_rows_only_when_patient_searches_by_shared_name() -> None:
    mine = _patient(full_name="Shared Name")
    _patient(full_name="Shared Name")

    response = get("/fhir/Patient?name=Shared", token_of(mine))

    assert response.json()["total"] == 1
    assert response["Cache-Control"] == "no-store"


def returns_every_patient_when_admin_searches() -> None:
    _patient()
    _patient()

    assert get("/fhir/Patient", token_of(role="ADMIN")).json()["total"] == 2


def returns_200_when_patient_changes_own_phone_and_birth_date() -> None:
    patient = _patient(phone="+49 30 1", date_of_birth=date(1990, 1, 1))
    body = get(f"/fhir/Patient/{patient.pk}", token_of(patient)).json()
    body["birthDate"] = "1991-02-03"
    body["telecom"] = [item for item in body["telecom"] if item["system"] != "phone"]
    body["telecom"].append({"system": "phone", "value": "+49 30 2"})

    response = send("put", f"/fhir/Patient/{patient.pk}", body, token_of(patient))

    patient.refresh_from_db()
    assert response.status_code == 200
    assert (patient.phone, patient.date_of_birth) == ("+49 30 2", date(1991, 2, 3))
    assert response["ETag"] == f'W/"{patient.version}"'


def returns_400_naming_name_when_patient_put_changes_the_name() -> None:
    patient = _patient(full_name="Before Name")
    body = get(f"/fhir/Patient/{patient.pk}", token_of(patient)).json()
    body["name"] = [{"text": "After Name"}]

    response = send("put", f"/fhir/Patient/{patient.pk}", body, token_of(patient))

    patient.refresh_from_db()
    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Patient.name"]
    assert patient.full_name == "Before Name"


def returns_200_when_admin_changes_the_name_as_the_console_does() -> None:
    patient = _patient(full_name="Before Name")
    admin = token_of(role="ADMIN")
    body = get(f"/fhir/Patient/{patient.pk}", admin).json()
    body["name"] = [{"text": "After Name"}]

    response = send("put", f"/fhir/Patient/{patient.pk}", body, admin)

    patient.refresh_from_db()
    assert response.status_code == 200
    assert patient.full_name == "After Name"


def returns_412_when_patient_put_has_a_stale_if_match() -> None:
    patient = _patient()
    token = token_of(patient)
    body = get(f"/fhir/Patient/{patient.pk}", token).json()

    response = send(
        "put",
        f"/fhir/Patient/{patient.pk}",
        body,
        token,
        **{"If-Match": f'W/"{patient.version + 9}"'},
    )

    assert response.status_code == 412


@pytest.mark.parametrize("method", ["post", "delete"])
def returns_405_when_patient_is_created_or_deleted(method: str) -> None:
    patient = _patient()
    token = token_of(patient)

    response = send(method, f"/fhir/Patient/{patient.pk}", {}, token)

    assert response.status_code == 405
    assert "PUT" in response["Allow"]


def returns_no_planted_value_in_logs_or_audit_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    patient = _patient(phone="+49 30 0", email=PLANTED_EMAIL, date_of_birth=date(1966, 6, 6))
    token = token_of(patient)
    caplog.set_level(logging.DEBUG)

    read = get(f"/fhir/Patient/{patient.pk}", token)
    search = get(f"/fhir/Patient?email={PLANTED_EMAIL}&phone=%2B49%20777%20313373", token)
    body = read.json()
    body["telecom"] = [
        {"system": "email", "value": PLANTED_EMAIL},
        {"system": "phone", "value": PLANTED_PHONE},
    ]
    body["birthDate"] = "1977-07-07"
    update = send("put", f"/fhir/Patient/{patient.pk}", body, token)
    body["name"] = [{"text": "PLANTED-LOG-NAME"}]
    failed = send("put", f"/fhir/Patient/{patient.pk}", body, token)

    assert [read.status_code, search.status_code, update.status_code, failed.status_code] == [
        200,
        200,
        200,
        400,
    ]
    logged = "\n".join(record.getMessage() + str(record.__dict__) for record in caplog.records)
    audit = " ".join(str(entry.metadata) for entry in AuditLogEntry.objects.all())
    for planted in (PLANTED_PHONE, PLANTED_EMAIL, "PLANTED-LOG-NAME", "1977-07-07", "1966-06-06"):
        assert planted not in logged
        assert planted not in audit
    assert "phone" in audit
