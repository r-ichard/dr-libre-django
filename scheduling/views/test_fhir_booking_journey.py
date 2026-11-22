"""Task 24d, spec 15.6: the whole booking journey through FHIR only, as a FHIR client sends it
(bearer token, no cookie, no Origin), then the audit trail of each step, read by an admin."""

from datetime import UTC, datetime, timedelta

import pytest

from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.models import Appointment
from scheduling.models.builders import Clinic, make, make_clinic, make_user
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, get, send, token_of

pytestmark = pytest.mark.django_db

HALF_HOUR = timedelta(minutes=30)
FIRST_DAY = datetime(2030, 1, 14, 9, 0, tzinfo=UTC)
BOOKED_AT = datetime(2030, 1, 14, 10, 0, tzinfo=UTC)
RESCHEDULED_AT = datetime(2030, 1, 14, 11, 0, tzinfo=UTC)
TAKEN_AT = datetime(2030, 1, 21, 10, 0, tzinfo=UTC)
OFFER_CATEGORY = "WAITLIST_OFFERED"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _instant(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_slot(clinic: Clinic, token: str) -> str:
    actor = f"Practitioner/{clinic.clinician.user_id}"
    query = f"service-type={clinic.appointment_type.pk}&schedule.actor={actor}"
    window = f"start=ge{_instant(FIRST_DAY)}&start=lt{_instant(FIRST_DAY + timedelta(hours=3))}"
    entries = get(f"/fhir/Slot?{query}&{window}", token).json()["entry"]
    return next(
        str(item["resource"]["id"])
        for item in entries
        if item["resource"]["start"].startswith("2030-01-14T10:00")
    )


def _booking(clinic: Clinic, slot_id: str) -> dict[str, object]:
    return {
        "resourceType": "Appointment",
        "status": "proposed",
        "serviceType": [{"coding": [{"code": str(clinic.appointment_type.pk)}]}],
        "slot": [{"reference": f"Slot/{slot_id}"}],
        "participant": [
            {"actor": {"reference": f"Patient/{clinic.patient.pk}"}, "status": "accepted"}
        ],
    }


def _change(key: str, token: str, **changes: object) -> dict[str, object]:
    body = get(f"/fhir/Appointment/{key}", token).json()
    body.update(changes)
    response = send("put", f"/fhir/Appointment/{key}", body, token)
    assert response.status_code == 200, response.content
    result: dict[str, object] = response.json()
    return result


def _join_waitlist(clinic: Clinic, token: str) -> str:
    body = {
        "resourceType": "Appointment",
        "status": "waitlist",
        "serviceType": [{"coding": [{"code": str(clinic.appointment_type.pk)}]}],
        "requestedPeriod": [
            {"start": _instant(TAKEN_AT - HALF_HOUR), "end": _instant(TAKEN_AT + HALF_HOUR)}
        ],
        "participant": [
            {"actor": {"reference": f"Patient/{clinic.patient.pk}"}, "status": "accepted"},
            {
                "actor": {"reference": f"Practitioner/{clinic.clinician.user_id}"},
                "status": "accepted",
            },
        ],
    }
    response = send("post", "/fhir/Appointment", body, token)
    assert response.status_code == 201, response.content
    assert response.json()["status"] == "waitlist"
    return str(response.json()["id"])


def _taken_slot(clinic: Clinic) -> Appointment:
    row = make(
        "Appointment",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        patient=make_user(role="PATIENT"),
        starts_at=TAKEN_AT,
        ends_at=TAKEN_AT + HALF_HOUR,
    )
    assert isinstance(row, Appointment)
    return row


def _audit(admin: str, action: str, entity_id: str) -> dict[str, object]:
    response = get(f"/fhir/AuditEvent?type={action}&entity={entity_id}", admin)
    assert response.json()["total"] == 1, (action, response.content)
    event: dict[str, object] = response.json()["entry"][0]["resource"]
    return event


def _agent(event: dict[str, object]) -> str:
    return str(event["agent"][0]["who"]["reference"])  # type: ignore[index]


def returns_the_whole_section_15_6_journey_and_one_audit_event_per_step_through_fhir_only() -> None:
    clinic = make_clinic()
    patient, clinician = token_of(clinic.patient), token_of(clinic.clinician.user)
    admin = token_of(role="ADMIN")
    taken = _taken_slot(clinic)

    slot_id = _find_slot(clinic, patient)
    booked = send("post", "/fhir/Appointment", _booking(clinic, slot_id), patient)
    key = str(booked.json()["id"])
    rescheduled = _change(
        key, patient, start=_instant(RESCHEDULED_AT), end=_instant(RESCHEDULED_AT + HALF_HOUR)
    )
    cancelled = _change(key, patient, status="cancelled", cancelationReason={"text": "Travel"})
    entry_id = _join_waitlist(clinic, patient)
    freed = send("put", f"/fhir/Appointment/{taken.pk}", _cancel_body(taken, clinician), clinician)
    offers = get(f"/fhir/Communication?category={OFFER_CATEGORY}", patient).json()["entry"]
    offered = get(f"/fhir/Appointment/{entry_id}", patient).json()
    acceptance = send("post", "/fhir/AppointmentResponse", _acceptance(entry_id, clinic), patient)
    communication = offers[0]["resource"]
    seen = send(
        "put",
        f"/fhir/Communication/{communication['id']}",
        {**communication, "received": _instant(NOW)},
        patient,
    )

    assert (booked.status_code, booked.json()["status"]) == (201, "booked")
    assert rescheduled["start"] == _instant(RESCHEDULED_AT)
    assert (cancelled["status"], cancelled["cancelationReason"]) == (
        "cancelled",
        {"text": "Travel"},
    )
    assert freed.status_code == 200
    assert len(offers) == 1
    assert communication["about"] == [{"reference": f"Appointment/{entry_id}"}]
    assert offered["status"] == "proposed"
    assert offered["start"] == _instant(TAKEN_AT)
    assert acceptance.status_code == 201
    assert get(f"/fhir/Appointment/{entry_id}", patient).json()["status"] == "booked"
    assert seen.status_code == 200
    assert get(f"/fhir/Communication/{communication['id']}", patient).json()["received"]
    assert Appointment.objects.get(waitlist_entry__pk=entry_id).status == AppointmentStatus.BOOKED
    steps = [
        ("appointment.book", key, patient_ref := f"Patient/{clinic.patient.pk}"),
        ("appointment.reschedule", key, patient_ref),
        ("appointment.cancel", key, patient_ref),
        ("waitlist.join", entry_id, patient_ref),
        ("waitlist.offer", entry_id, f"Practitioner/{clinic.clinician.user_id}"),
        ("waitlist.accept", entry_id, patient_ref),
        ("notification.read", str(communication["id"]), patient_ref),
    ]
    for action, entity_id, agent in steps:
        event = _audit(admin, action, entity_id)
        assert _agent(event).endswith(agent.split("/")[1]), action


def _cancel_body(row: Appointment, token: str) -> dict[str, object]:
    body: dict[str, object] = get(f"/fhir/Appointment/{row.pk}", token).json()
    body.update(status="cancelled", cancelationReason={"text": "Clinic closed"})
    return body


def _acceptance(entry_id: str, clinic: Clinic) -> dict[str, object]:
    return {
        "resourceType": "AppointmentResponse",
        "appointment": {"reference": f"Appointment/{entry_id}"},
        "actor": {"reference": f"Patient/{clinic.patient.pk}"},
        "participantStatus": "accepted",
    }
