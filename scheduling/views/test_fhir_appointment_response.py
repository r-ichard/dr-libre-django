"""Task 24, spec 15.2, 15.4, 5.8: a waitlist offer is accepted through `AppointmentResponse`, by the
`accept_offer` use case, as a FHIR client sends it (bearer token, no cookie, no Origin)."""

from datetime import datetime

import pytest

from scheduling.models import Appointment, WaitlistEntry
from scheduling.models.builders import Clinic, make_clinic, make_user
from scheduling.use_cases.test_waitlist_support import (
    _booked_slot,
    _cancelled_slot,
    _offered_entry,
)
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, get, send, token_of

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _offer(clinic: Clinic) -> WaitlistEntry:
    return _offered_entry(clinic, _cancelled_slot(clinic))


def _acceptance(entry: WaitlistEntry, status: str = "accepted") -> dict[str, object]:
    return {
        "resourceType": "AppointmentResponse",
        "appointment": {"reference": f"Appointment/{entry.pk}"},
        "actor": {"reference": f"Patient/{entry.patient_id}"},
        "participantStatus": status,
    }


def returns_201_with_booked_appointment_under_the_entry_id_when_patient_accepts_own_offer() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)

    response = send(
        "post", "/fhir/AppointmentResponse", _acceptance(entry), token_of(clinic.patient)
    )

    assert response.status_code == 201
    assert response.json()["participantStatus"] == "accepted"
    assert response.json()["appointment"]["reference"] == f"Appointment/{entry.pk}"
    assert Appointment.objects.get(waitlist_entry=entry).status == "BOOKED"
    booked = get(f"/fhir/Appointment/{entry.pk}", token_of(clinic.patient))
    assert booked.json()["status"] == "booked"


def returns_201_when_admin_accepts_the_offer_for_the_patient() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)

    response = send("post", "/fhir/AppointmentResponse", _acceptance(entry), token_of(role="ADMIN"))

    assert response.status_code == 201
    assert Appointment.objects.get(waitlist_entry=entry).patient_id == clinic.patient.pk


def returns_409_when_the_offer_is_accepted_a_second_time() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)
    token = token_of(clinic.patient)
    send("post", "/fhir/AppointmentResponse", _acceptance(entry), token)

    response = send("post", "/fhir/AppointmentResponse", _acceptance(entry), token)

    assert response.status_code == 409
    assert response.json()["resourceType"] == "OperationOutcome"
    assert Appointment.objects.filter(waitlist_entry=entry).count() == 1


def returns_409_and_books_nothing_when_someone_else_took_the_slot() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)
    _booked_slot(clinic)

    response = send(
        "post", "/fhir/AppointmentResponse", _acceptance(entry), token_of(clinic.patient)
    )

    assert response.status_code == 409
    assert not Appointment.objects.filter(waitlist_entry=entry).exists()


def returns_403_when_another_patient_accepts_the_offer() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)
    stranger = make_user(role="PATIENT")

    response = send("post", "/fhir/AppointmentResponse", _acceptance(entry), token_of(stranger))

    assert response.status_code == 403
    assert WaitlistEntry.objects.get(pk=entry.pk).status == "OFFERED"


def returns_400_naming_participant_status_when_the_response_declines() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)

    response = send(
        "post",
        "/fhir/AppointmentResponse",
        _acceptance(entry, "declined"),
        token_of(clinic.patient),
    )

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["AppointmentResponse.participantStatus"]
    assert WaitlistEntry.objects.get(pk=entry.pk).status == "OFFERED"


def returns_401_when_the_response_is_posted_without_token() -> None:
    entry = _offer(make_clinic())

    assert send("post", "/fhir/AppointmentResponse", _acceptance(entry), None).status_code == 401


def returns_403_when_a_clinician_accepts() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)

    response = send(
        "post", "/fhir/AppointmentResponse", _acceptance(entry), token_of(clinic.clinician.user)
    )

    assert response.status_code == 403


def returns_the_booked_response_to_its_patient_and_hides_it_from_another() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)
    send("post", "/fhir/AppointmentResponse", _acceptance(entry), token_of(clinic.patient))
    stranger = token_of(make_user(role="PATIENT"))

    own = get(f"/fhir/AppointmentResponse/{entry.pk}", token_of(clinic.patient))
    foreign = get(f"/fhir/AppointmentResponse/{entry.pk}", stranger)
    own_search = get("/fhir/AppointmentResponse", token_of(clinic.patient)).json()
    foreign_search = get("/fhir/AppointmentResponse", stranger).json()

    assert own.status_code == 200
    assert own.json()["participantStatus"] == "accepted"
    assert foreign.status_code == 403
    assert own_search["total"] == 1
    assert foreign_search["total"] == 0


@pytest.mark.parametrize("method", ["put", "delete"])
def returns_405_when_a_response_is_updated_or_deleted(method: str) -> None:
    clinic = make_clinic()
    entry = _offer(clinic)

    response = send(
        method, f"/fhir/AppointmentResponse/{entry.pk}", _acceptance(entry), token_of(role="ADMIN")
    )

    assert response.status_code == 405


def returns_the_patient_as_actor_and_the_appointment_times_and_version_when_response_is_read() -> (
    None
):
    clinic = make_clinic()
    entry = _offer(clinic)
    token = token_of(clinic.patient)
    send("post", "/fhir/AppointmentResponse", _acceptance(entry), token)
    appointment = Appointment.objects.get(waitlist_entry=entry)

    body = get(f"/fhir/AppointmentResponse/{entry.pk}", token).json()
    booked = get(f"/fhir/Appointment/{entry.pk}", token).json()

    assert body["actor"] == {"reference": f"Patient/{clinic.patient.pk}"}
    assert datetime.fromisoformat(body["start"]) == appointment.starts_at
    assert datetime.fromisoformat(body["end"]) == appointment.ends_at
    assert body["meta"]["versionId"] == booked["meta"]["versionId"]


def returns_400_naming_appointment_when_the_reference_is_not_an_appointment() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)
    body = {**_acceptance(entry), "appointment": {"reference": f"Patient/{entry.pk}"}}

    response = send("post", "/fhir/AppointmentResponse", body, token_of(clinic.patient))

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["AppointmentResponse.appointment"]


def returns_400_naming_actor_when_the_actor_is_not_the_entrys_patient() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)
    stranger = make_user(role="PATIENT")
    body = {**_acceptance(entry), "actor": {"reference": f"Patient/{stranger.pk}"}}

    response = send("post", "/fhir/AppointmentResponse", body, token_of(role="ADMIN"))

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["AppointmentResponse.actor"]
    assert WaitlistEntry.objects.get(pk=entry.pk).status == "OFFERED"


def returns_403_not_400_when_a_stranger_names_the_entrys_patient_as_actor() -> None:
    clinic = make_clinic()
    entry = _offer(clinic)
    stranger = make_user(role="PATIENT")

    response = send("post", "/fhir/AppointmentResponse", _acceptance(entry), token_of(stranger))
    own_name = {**_acceptance(entry), "actor": {"reference": f"Patient/{stranger.pk}"}}
    own_response = send("post", "/fhir/AppointmentResponse", own_name, token_of(stranger))

    assert (response.status_code, own_response.status_code) == (403, 403)
