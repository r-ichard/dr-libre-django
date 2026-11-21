"""Section 14: POST /waitlist, /waitlist/{id}/accept and /offer, as a caller sees them."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from django.test import Client

from scheduling.models import AuditLogEntry, Notification, User, WaitlistEntry
from scheduling.models.builders import add_clinician, make, make_clinic
from scheduling.use_cases.test_waitlist_support import (
    FOREIGN_REASON,
    ONE_DAY,
    SLOT,
    _cancelled_slot,
    _entry_for,
    _offered_entry,
)
from scheduling.views import clock
from scheduling.views.test_appointment_support import (
    NOW,
    _admin,
    _clinician_user,
    _error_code,
    _signed_in,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

WAITLIST = "/api/v1/waitlist"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _join_body(clinic_type_id: object, **overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "appointment_type_id": str(clinic_type_id),
        "earliest_at": (SLOT - ONE_DAY).isoformat(),
        "latest_at": (SLOT + ONE_DAY).isoformat(),
    }
    return {**fields, **overrides}


def _join(client: Client, body: Mapping[str, object]) -> _MonkeyPatchedWSGIResponse:
    return client.post(WAITLIST, body, content_type="application/json")


def _stranger() -> User:
    stranger = make("User")
    assert isinstance(stranger, User)
    return stranger


def _act(client: Client, entry: WaitlistEntry, action: str) -> _MonkeyPatchedWSGIResponse:
    return client.post(f"{WAITLIST}/{entry.pk}/{action}", {}, content_type="application/json")


# --- join ---


def returns_401_when_joining_without_session() -> None:
    assert _join(Client(), {}).status_code == 401


def returns_201_when_patient_joins() -> None:
    clinic = make_clinic()

    response = _join(_signed_in(clinic.patient), _join_body(clinic.appointment_type.pk))

    body = response.json()
    entry = WaitlistEntry.objects.get()
    assert response.status_code == 201
    assert body["id"] == str(entry.pk)
    assert body["status"] == "WAITING"
    assert body["appointment_type_id"] == str(clinic.appointment_type.pk)
    assert body["preferred_clinician_id"] is None
    assert datetime.fromisoformat(body["earliest_at"]) == SLOT - ONE_DAY
    assert datetime.fromisoformat(body["latest_at"]) == SLOT + ONE_DAY
    assert body["offer"] is None
    assert entry.patient_id == clinic.patient.pk


def returns_201_for_named_patient_when_admin_joins() -> None:
    clinic = make_clinic()
    body = _join_body(clinic.appointment_type.pk, patient_id=str(clinic.patient.pk))

    response = _join(_signed_in(_admin()), body)

    assert response.status_code == 201
    assert WaitlistEntry.objects.get().patient_id == clinic.patient.pk


def returns_403_when_clinician_joins() -> None:
    clinic = make_clinic()
    body = _join_body(clinic.appointment_type.pk, patient_id=str(clinic.patient.pk))

    response = _join(_signed_in(_clinician_user(clinic)), body)

    assert response.status_code == 403
    assert _error_code(response) == "forbidden"
    assert WaitlistEntry.objects.count() == 0


def returns_403_when_patient_names_another_patient() -> None:
    clinic = make_clinic()
    body = _join_body(clinic.appointment_type.pk, patient_id=str(make("User").pk))

    assert _join(_signed_in(clinic.patient), body).status_code == 403


def returns_404_when_type_inactive() -> None:
    clinic = make_clinic(type_fields={"is_active": False})

    response = _join(_signed_in(clinic.patient), _join_body(clinic.appointment_type.pk))

    assert response.status_code == 404
    assert _error_code(response) == "not_found"


def returns_404_when_preferred_clinician_inactive() -> None:
    clinic = make_clinic()
    gone = add_clinician(clinic.department, user=make("User", role="CLINICIAN", is_active=False))
    body = _join_body(clinic.appointment_type.pk, preferred_clinician_id=str(gone.pk))

    assert _join(_signed_in(clinic.patient), body).status_code == 404


def returns_400_when_unknown_field() -> None:
    clinic = make_clinic()
    body = _join_body(clinic.appointment_type.pk, status="BOOKED")

    response = _join(_signed_in(clinic.patient), body)

    assert response.status_code == 400
    assert _error_code(response) == "invalid_input"
    assert WaitlistEntry.objects.count() == 0


def returns_400_when_window_instant_has_no_time_zone() -> None:
    clinic = make_clinic()
    body = _join_body(clinic.appointment_type.pk, earliest_at="2030-01-06T10:00:00")

    assert _join(_signed_in(clinic.patient), body).status_code == 400


def returns_400_when_type_id_missing() -> None:
    clinic = make_clinic()
    body = _join_body(clinic.appointment_type.pk)
    del body["appointment_type_id"]

    assert _join(_signed_in(clinic.patient), body).status_code == 400


# --- accept ---


def returns_200_booked_when_patient_accepts() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    response = _act(_signed_in(clinic.patient), entry, "accept")

    assert response.status_code == 200
    assert response.json()["status"] == "BOOKED"
    assert response.json()["offer"] is None


def returns_403_when_other_patient_accepts() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    response = _act(_signed_in(_stranger()), entry, "accept")

    assert response.status_code == 403
    entry.refresh_from_db()
    assert entry.status == "OFFERED"


def returns_200_when_admin_accepts() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    assert _act(_signed_in(_admin()), entry, "accept").status_code == 200


def returns_409_conflict_when_slot_taken() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))
    make(
        "Appointment",
        appointment_type=clinic.appointment_type,
        clinician=clinic.clinician,
        starts_at=SLOT,
        ends_at=SLOT + timedelta(minutes=30),
    )

    response = _act(_signed_in(clinic.patient), entry, "accept")

    assert response.status_code == 409
    assert _error_code(response) == "conflict"
    entry.refresh_from_db()
    assert entry.status == "OFFERED"


def returns_409_invalid_transition_when_accepting_entry_not_offered() -> None:
    clinic = make_clinic()
    entry = _entry_for(clinic)

    response = _act(_signed_in(clinic.patient), entry, "accept")

    assert response.status_code == 409
    assert _error_code(response) == "invalid_transition"


def returns_404_when_accepting_unknown_entry() -> None:
    clinic = make_clinic()
    entry = _entry_for(clinic)
    entry.delete()

    assert _act(_signed_in(clinic.patient), entry, "accept").status_code == 404


def returns_400_when_accept_body_has_a_field() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    response = _signed_in(clinic.patient).post(
        f"{WAITLIST}/{entry.pk}/accept", {"patient_id": "x"}, content_type="application/json"
    )

    assert response.status_code == 400


# --- offer ---


def returns_200_offered_with_time_provider_and_hospital_when_admin_offers() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    entry = _entry_for(clinic)

    response = _act(_signed_in(_admin()), entry, "offer")

    offer = response.json()["offer"]
    hospital = clinic.department.hospital
    assert response.status_code == 200
    assert response.json()["status"] == "OFFERED"
    assert datetime.fromisoformat(offer["starts_at"]) == SLOT
    assert datetime.fromisoformat(offer["ends_at"]) == SLOT + timedelta(minutes=30)
    assert offer["time_zone"] == "Europe/Berlin"
    assert offer["provider_name"] == clinic.clinician.user.full_name
    assert offer["hospital_name"] == hospital.name
    assert set(offer) == {"starts_at", "ends_at", "time_zone", "provider_name", "hospital_name"}


def returns_no_foreign_reason_or_ids_when_offer_shown() -> None:
    clinic = make_clinic()
    freed = _cancelled_slot(clinic)
    entry = _entry_for(clinic)

    response = _act(_signed_in(_admin()), entry, "offer")

    assert response.status_code == 200
    text = response.content.decode()
    assert FOREIGN_REASON not in text
    assert str(freed.pk) not in text
    assert str(freed.patient_id) not in text
    assert "patient_reason" not in text


def returns_no_foreign_reason_when_patient_accepts_and_notification_is_read() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    entry = _entry_for(clinic)
    _act(_signed_in(_admin()), entry, "offer")

    notification = Notification.objects.get(kind="WAITLIST_OFFERED")

    assert FOREIGN_REASON not in f"{notification.title} {notification.body}"
    assert AuditLogEntry.objects.filter(action="waitlist.offer").count() == 1


def returns_403_when_patient_offers() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    entry = _entry_for(clinic)

    response = _act(_signed_in(clinic.patient), entry, "offer")

    assert response.status_code == 403
    assert _error_code(response) == "forbidden"


def returns_403_when_clinician_offers() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    entry = _entry_for(clinic)

    assert _act(_signed_in(_clinician_user(clinic)), entry, "offer").status_code == 403


def returns_409_no_clinician_available_when_nothing_to_offer() -> None:
    clinic = make_clinic()
    entry = _entry_for(clinic)

    response = _act(_signed_in(_admin()), entry, "offer")

    assert response.status_code == 409
    assert _error_code(response) == "no_clinician_available"


def returns_401_when_offering_without_session() -> None:
    clinic = make_clinic()
    entry = _entry_for(clinic)

    assert _act(Client(), entry, "offer").status_code == 401


def returns_409_invalid_transition_when_offering_entry_already_offered() -> None:
    clinic = make_clinic()
    freed = _cancelled_slot(clinic)
    entry = _offered_entry(clinic, freed)

    response = _act(_signed_in(_admin()), entry, "offer")

    assert response.status_code == 409
    assert _error_code(response) == "invalid_transition"
