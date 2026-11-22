"""Task 23a, spec 15.6 items 6, 7 and 11: every way to book over FHIR, and every refusal of the
booking use case reaching the client as an OperationOutcome that names it."""

from datetime import timedelta

import pytest

from scheduling.domain.fhir_slot_id import slot_id
from scheduling.models import Appointment, AvailabilityRule
from scheduling.models.builders import STARTS_AT, add_clinician, make, make_clinic, make_user
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, get, send, token_of

pytestmark = pytest.mark.django_db

MONDAY_TEN = "2030-01-07T10:00:00Z"
OFF_THE_GRID = "2030-01-07T10:05:00Z"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _body(
    clinic: object, practitioner: object = "clinic", patient: object = "clinic", **more: object
) -> dict[str, object]:
    person = clinic.patient if patient == "clinic" else patient  # type: ignore[attr-defined]
    named = clinic.clinician if practitioner == "clinic" else practitioner  # type: ignore[attr-defined]
    participants = [{"actor": {"reference": f"Patient/{person.pk}"}, "status": "accepted"}]  # type: ignore[union-attr]
    if named is not None:
        participants.append(
            {"actor": {"reference": f"Practitioner/{named.user_id}"}, "status": "accepted"}  # type: ignore[union-attr]
        )
    return {
        "resourceType": "Appointment",
        "status": "proposed",
        "start": MONDAY_TEN,
        "serviceType": [{"coding": [{"code": str(clinic.appointment_type.pk)}]}],  # type: ignore[attr-defined]
        "participant": participants,
        **more,
    }


def _post(body: dict[str, object], token: str) -> object:
    return send("post", "/fhir/Appointment", body, token)


def _extension_codes(response: object) -> list[object]:
    issue = response.json()["issue"][0]  # type: ignore[attr-defined]
    return [item["valueCode"] for item in issue["extension"]]


def _slot_reference(clinic: object) -> str:
    rule = AvailabilityRule.objects.get(clinician=clinic.clinician)  # type: ignore[attr-defined]
    return f"Slot/{slot_id(rule.pk, clinic.appointment_type.pk, STARTS_AT)}"  # type: ignore[attr-defined]


def returns_201_with_the_slots_clinician_when_patient_books_by_slot_reference() -> None:
    clinic = make_clinic()
    body = _body(clinic, practitioner=None, slot=[{"reference": _slot_reference(clinic)}])

    response = _post(body, token_of(clinic.patient))

    assert response.status_code == 201  # type: ignore[attr-defined]
    assert Appointment.objects.get().clinician_id == clinic.clinician.pk


def returns_400_and_no_appointment_when_slot_and_practitioner_name_different_clinicians() -> None:
    clinic = make_clinic()
    other = add_clinician(clinic.department)
    body = _body(clinic, practitioner=other, slot=[{"reference": _slot_reference(clinic)}])

    response = _post(body, token_of(clinic.patient))

    assert response.status_code == 400  # type: ignore[attr-defined]
    assert response.json()["issue"][0]["expression"] == ["Appointment.slot"]  # type: ignore[attr-defined]
    assert not Appointment.objects.exists()


def returns_201_with_an_assigned_practitioner_when_patient_books_first_available() -> None:
    clinic = make_clinic()

    response = _post(_body(clinic, practitioner=None), token_of(clinic.patient))

    assert response.status_code == 201  # type: ignore[attr-defined]
    assert Appointment.objects.get().clinician_id == clinic.clinician.pk
    references = [item["actor"]["reference"] for item in response.json()["participant"]]  # type: ignore[attr-defined]
    assert f"Practitioner/{clinic.clinician.user_id}" in references


def returns_no_appointment_when_admin_books_without_a_practitioner() -> None:
    clinic = make_clinic()

    response = _post(_body(clinic, practitioner=None), token_of(role="ADMIN"))

    assert response.status_code in {400, 403}  # type: ignore[attr-defined]
    assert not Appointment.objects.exists()


def returns_201_in_the_own_calendar_when_clinician_books_without_naming_a_practitioner() -> None:
    clinic = make_clinic()
    other = add_clinician(clinic.department)

    response = _post(_body(clinic, practitioner=None), token_of(other.user))

    assert response.status_code == 201  # type: ignore[attr-defined]
    assert Appointment.objects.get().clinician_id == other.pk


def returns_201_when_clinician_books_into_the_own_calendar_for_a_patient() -> None:
    clinic = make_clinic()

    response = _post(_body(clinic), token_of(clinic.clinician.user))

    assert response.status_code == 201  # type: ignore[attr-defined]
    created = Appointment.objects.get()
    assert (created.clinician_id, created.patient_id) == (clinic.clinician.pk, clinic.patient.pk)


def returns_403_and_no_appointment_when_clinician_books_into_another_calendar() -> None:
    clinic = make_clinic()
    other = add_clinician(clinic.department)

    response = _post(_body(clinic, practitioner=other), token_of(clinic.clinician.user))

    assert response.status_code == 403  # type: ignore[attr-defined]
    assert not Appointment.objects.exists()


def returns_201_when_admin_books_a_named_clinician_for_an_active_patient() -> None:
    clinic = make_clinic()

    response = _post(_body(clinic), token_of(role="ADMIN"))

    assert response.status_code == 201  # type: ignore[attr-defined]
    created = Appointment.objects.get()
    assert (created.clinician_id, created.patient_id) == (clinic.clinician.pk, clinic.patient.pk)


def returns_no_appointment_when_admin_books_for_an_inactive_patient() -> None:
    clinic = make_clinic()
    dormant = make_user(role="PATIENT", is_active=False)

    response = _post(_body(clinic, patient=dormant), token_of(role="ADMIN"))

    assert response.status_code in {400, 403, 404}  # type: ignore[attr-defined]
    assert not Appointment.objects.exists()


def returns_422_naming_lead_time_too_short_when_patient_books_inside_two_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = make_clinic()
    monkeypatch.setattr(clock, "now_utc", lambda: STARTS_AT - timedelta(minutes=60))

    response = _post(_body(clinic), token_of(clinic.patient))

    assert response.status_code == 422  # type: ignore[attr-defined]
    assert "lead_time_too_short" in _extension_codes(response)


def returns_422_naming_too_many_open_bookings_when_patient_has_three() -> None:
    clinic = make_clinic()
    for days in (1, 2, 3):
        later = STARTS_AT + timedelta(days=days)
        make(
            "Appointment",
            patient=clinic.patient,
            clinician=add_clinician(clinic.department),
            appointment_type=clinic.appointment_type,
            starts_at=later,
            ends_at=later + timedelta(minutes=30),
        )

    response = _post(_body(clinic), token_of(clinic.patient))

    assert response.status_code == 422  # type: ignore[attr-defined]
    assert "too_many_open_bookings" in _extension_codes(response)


def returns_422_naming_type_not_bookable_online_when_patient_books_such_a_type() -> None:
    clinic = make_clinic(type_fields={"is_bookable_online": False})

    response = _post(_body(clinic), token_of(clinic.patient))

    assert response.status_code == 422  # type: ignore[attr-defined]
    assert "type_not_bookable_online" in _extension_codes(response)


def returns_422_naming_outside_availability_when_start_is_off_the_grid() -> None:
    clinic = make_clinic()

    response = _post(_body(clinic, start=OFF_THE_GRID), token_of(clinic.patient))

    assert response.status_code == 422  # type: ignore[attr-defined]
    assert "outside_availability" in _extension_codes(response)


def returns_422_naming_cancellation_window_closed_when_patient_cancels_inside_24_hours() -> None:
    clinic = make_clinic()
    row = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
    )
    token = token_of(clinic.patient)
    body = get(f"/fhir/Appointment/{row.pk}", token).json()
    body.update(status="cancelled", cancelationReason={"text": "Travel"})

    response = send(
        "put",
        f"/fhir/Appointment/{row.pk}",
        body,
        token,
        **{"If-Match": f'W/"{row.version}"'},  # type: ignore[attr-defined]
    )

    assert response.status_code == 422
    assert "cancellation_window_closed" in _extension_codes(response)


def returns_409_naming_the_clinician_when_the_slot_is_taken() -> None:
    clinic = make_clinic()
    make(
        "Appointment",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        patient=make_user(role="PATIENT"),
    )

    response = _post(_body(clinic), token_of(clinic.patient))

    assert response.status_code == 409  # type: ignore[attr-defined]
    assert "clinician" in _extension_codes(response)


def returns_409_naming_no_room_available_when_the_type_needs_a_room_and_none_is_free() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})

    response = _post(_body(clinic), token_of(clinic.patient))

    assert response.status_code == 409  # type: ignore[attr-defined]
    assert "no_room_available" in _extension_codes(response)
    assert not Appointment.objects.exists()


def returns_409_naming_no_clinician_available_when_every_clinician_is_busy() -> None:
    clinic = make_clinic()
    make(
        "Appointment",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        patient=make_user(role="PATIENT"),
    )

    response = _post(_body(clinic, practitioner=None), token_of(clinic.patient))

    assert response.status_code == 409  # type: ignore[attr-defined]
    assert "no_clinician_available" in _extension_codes(response)
