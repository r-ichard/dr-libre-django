"""Section 5.6 and 14: cancel, reschedule and status actions, driven through the API so each test
states what a caller sees. Emails of these changes: test_appointment_emails.py."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import timedelta

import pytest
from django.core import mail
from django.db import connection
from django.db.models import F
from django.test.utils import CaptureQueriesContext

from scheduling.models import Appointment, AuditLogEntry, Notification, User
from scheduling.models.builders import add_clinician, make, make_clinic
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client
from scheduling.views.test_appointment_support import (
    APPOINTMENTS,
    MONDAY_AFTER,
    NEXT_MONDAY,
    NOW,
    THIRTY_MINUTES,
    _admin,
    _cancel,
    _clinician_user,
    _error_code,
    _make_appointment,
    _post,
    _reschedule,
    _signed_in,
    _status_of,
)

pytestmark = pytest.mark.django_db

PLANTED_REASON = "planted-cancel-reason-7731"
OnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


# --- cancel ---


def returns_200_and_records_cancellation_when_patient_cancels_25_hours_ahead() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=25))
    version_before = appointment.version

    response = _cancel(_signed_in(clinic.patient), appointment, PLANTED_REASON)

    appointment.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert appointment.status == "CANCELLED"
    assert appointment.cancelled_at == NOW
    assert appointment.cancellation_reason == PLANTED_REASON
    assert appointment.version == version_before + 1


def returns_200_when_patient_cancels_exactly_24_hours_ahead() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=24))

    response = _cancel(_signed_in(clinic.patient), appointment)

    assert response.status_code == 200


def returns_422_cancellation_window_closed_when_patient_cancels_23h59m_ahead() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(
        clinic, starts_at=NOW + timedelta(hours=24) - timedelta(minutes=1)
    )

    response = _cancel(_signed_in(clinic.patient), appointment)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["violated_rules"] == ["cancellation_window_closed"]
    assert _status_of(appointment) == "BOOKED"


def returns_200_when_appointment_clinician_cancels_inside_24_hours() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=2))

    response = _cancel(_signed_in(_clinician_user(clinic)), appointment)

    assert response.status_code == 200


def returns_200_when_admin_cancels_inside_24_hours() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=2))

    response = _cancel(_signed_in(_admin()), appointment)

    assert response.status_code == 200


def returns_403_when_patient_cancels_someone_elses_appointment() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=48))

    response = _cancel(_signed_in(make("User")), appointment)  # type: ignore[arg-type]

    assert response.status_code == 403
    assert _status_of(appointment) == "BOOKED"


def returns_403_when_other_clinician_cancels() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=48))
    other = add_clinician(clinic.department)
    other_user = other.user
    assert isinstance(other_user, User)
    other_user.refresh_from_db()

    response = _cancel(_signed_in(other_user), appointment)

    assert response.status_code == 403


def returns_400_when_cancel_reason_is_blank() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=48))

    response = _cancel(_signed_in(clinic.patient), appointment, "   ")

    assert response.status_code == 400
    assert _error_code(response) == "invalid_input"


def returns_400_when_cancel_body_has_unknown_field() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=48))

    response = _post(
        _signed_in(clinic.patient), appointment, "cancel", {"reason": "x", "status": "BOOKED"}
    )

    assert response.status_code == 400
    assert _error_code(response) == "invalid_input"


def returns_401_when_cancelling_without_session() -> None:
    appointment = _make_appointment(make_clinic())

    response = _cancel(browser_api_client(), appointment)

    assert response.status_code == 401


@pytest.mark.parametrize("status", ["COMPLETED", "CANCELLED", "NO_SHOW"])
def returns_409_invalid_transition_with_current_status_when_cancelling_a_closed_appointment(
    status: str,
) -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=48))
    Appointment.objects.filter(pk=appointment.pk).update(
        version=F("version") + 1,
        status=status,
        cancelled_at=NOW if status == "CANCELLED" else None,
        cancellation_reason="earlier" if status == "CANCELLED" else "",
    )

    response = _cancel(_signed_in(_admin()), appointment)

    assert response.status_code == 409
    assert _error_code(response) == "invalid_transition"
    assert response.json()["error"]["details"]["current_status"] == status


def returns_audit_entry_without_the_reason_when_cancelling() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=48))

    _cancel(_signed_in(clinic.patient), appointment, PLANTED_REASON)

    entries = AuditLogEntry.objects.filter(
        action="appointment.cancel", entity_id=str(appointment.pk)
    )
    assert entries.count() == 1
    assert PLANTED_REASON not in str(list(AuditLogEntry.objects.values_list("metadata", flat=True)))


def returns_cancelled_notification_with_time_only_text_when_cancelling() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=48))

    _cancel(_signed_in(clinic.patient), appointment, PLANTED_REASON)

    notification = Notification.objects.get(appointment=appointment, title="Appointment cancelled")
    assert notification.kind == "APPOINTMENT_CANCELLED"
    assert notification.recipient_id == clinic.patient.pk
    for forbidden in (PLANTED_REASON, clinic.patient.full_name, clinic.patient.email):
        assert forbidden not in notification.body
    assert "9 January 2030" in notification.body


# --- reschedule ---


def returns_200_and_moves_appointment_keeping_clinician_and_type_when_slot_is_free() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY)
    version_before = appointment.version

    response = _reschedule(_signed_in(clinic.patient), appointment, MONDAY_AFTER)

    appointment.refresh_from_db()
    assert response.status_code == 200
    assert appointment.starts_at == MONDAY_AFTER
    assert appointment.ends_at == MONDAY_AFTER + THIRTY_MINUTES
    assert appointment.clinician_id == clinic.clinician.pk
    assert appointment.appointment_type_id == clinic.appointment_type.pk
    assert appointment.version == version_before + 1


def returns_200_when_new_slot_overlaps_the_appointments_own_old_slot() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY)
    overlapping = NEXT_MONDAY + timedelta(minutes=15)

    response = _reschedule(_signed_in(clinic.patient), appointment, overlapping)

    assert response.status_code == 200
    assert _status_of(appointment) == "BOOKED"


def returns_409_conflict_and_changes_nothing_when_new_slot_is_taken() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY)
    _make_appointment(clinic, starts_at=MONDAY_AFTER, patient=make("User"))
    notifications_before = Notification.objects.count()

    response = _reschedule(_signed_in(clinic.patient), appointment, MONDAY_AFTER)

    appointment.refresh_from_db()
    assert response.status_code == 409
    assert _error_code(response) == "conflict"
    assert appointment.starts_at == NEXT_MONDAY
    assert Notification.objects.count() == notifications_before


def returns_422_when_new_slot_is_outside_availability() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY)
    at_night = MONDAY_AFTER.replace(hour=2)

    response = _reschedule(_signed_in(_admin()), appointment, at_night)

    assert response.status_code == 422
    assert _status_of(appointment) == "BOOKED"


def returns_422_cancellation_window_closed_when_patient_reschedules_inside_24_hours() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NOW + timedelta(hours=10))

    response = _reschedule(_signed_in(clinic.patient), appointment, MONDAY_AFTER)

    assert response.status_code == 422
    assert "cancellation_window_closed" in response.json()["error"]["details"]["violated_rules"]


def returns_409_invalid_transition_when_rescheduling_a_checked_in_appointment() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY, status="CHECKED_IN")

    response = _reschedule(_signed_in(_admin()), appointment, MONDAY_AFTER)

    assert response.status_code == 409
    assert response.json()["error"]["details"]["current_status"] == "CHECKED_IN"


def returns_400_when_reschedule_start_has_no_offset() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY)

    response = _post(
        _signed_in(clinic.patient), appointment, "reschedule", {"starts_at": "2030-01-21T10:00:00"}
    )

    assert response.status_code == 400


def returns_rescheduled_notification_and_audit_entry_when_rescheduling() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY)

    _reschedule(_signed_in(clinic.patient), appointment, MONDAY_AFTER)

    notification = Notification.objects.get(
        appointment=appointment, title="Appointment rescheduled"
    )
    assert notification.kind == "SCHEDULE_CHANGED"
    assert "21 January 2030" in notification.body
    assert AuditLogEntry.objects.filter(action="appointment.reschedule").count() == 1


# --- status actions ---


@pytest.mark.parametrize(
    ("action", "start_status", "end_status"),
    [
        ("check-in", "BOOKED", "CHECKED_IN"),
        ("check-in", "CONFIRMED", "CHECKED_IN"),
        ("complete", "CHECKED_IN", "COMPLETED"),
        ("no-show", "BOOKED", "NO_SHOW"),
        ("no-show", "CONFIRMED", "NO_SHOW"),
    ],
)
def returns_200_and_new_status_when_appointment_clinician_changes_status(
    action: str, start_status: str, end_status: str
) -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, status=start_status)
    version_before = appointment.version

    response = _post(_signed_in(_clinician_user(clinic)), appointment, action)

    appointment.refresh_from_db()
    assert response.status_code == 200
    assert appointment.status == end_status
    assert appointment.version == version_before + 1
    assert Notification.objects.filter(appointment=appointment).count() == 0
    assert mail.outbox == []


@pytest.mark.parametrize("action", ["check-in", "complete", "no-show"])
def returns_403_when_patient_changes_status_of_own_appointment(action: str) -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, status="CHECKED_IN")

    response = _post(_signed_in(clinic.patient), appointment, action)

    assert response.status_code == 403
    assert _status_of(appointment) == "CHECKED_IN"


def returns_403_when_other_clinician_checks_in() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic)
    other_user = add_clinician(clinic.department).user
    assert isinstance(other_user, User)
    other_user.refresh_from_db()

    response = _post(_signed_in(other_user), appointment, "check-in")

    assert response.status_code == 403


def returns_200_when_admin_checks_in_any_appointment() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic)

    response = _post(_signed_in(_admin()), appointment, "check-in")

    assert response.status_code == 200
    assert _status_of(appointment) == "CHECKED_IN"


@pytest.mark.parametrize(
    ("action", "status"),
    [
        ("complete", "BOOKED"),
        ("check-in", "CHECKED_IN"),
        ("no-show", "CHECKED_IN"),
        ("check-in", "COMPLETED"),
        ("complete", "COMPLETED"),
        ("no-show", "CANCELLED"),
    ],
)
def returns_409_invalid_transition_with_current_status_when_table_forbids_the_change(
    action: str, status: str
) -> None:
    clinic = make_clinic()
    closed_fields = {"cancelled_at": NOW, "cancellation_reason": "earlier"}
    appointment = _make_appointment(
        clinic, status=status, **(closed_fields if status == "CANCELLED" else {})
    )

    response = _post(_signed_in(_admin()), appointment, action)

    assert response.status_code == 409
    assert _error_code(response) == "invalid_transition"
    assert response.json()["error"]["details"]["current_status"] == status


def returns_404_when_status_action_names_no_appointment() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic)
    admin_client = _signed_in(_admin())
    assert _post(admin_client, appointment, "check-in").status_code == 200
    appointment.delete()

    response = _post(admin_client, appointment, "check-in")

    assert response.status_code == 404
    assert _error_code(response) == "not_found"


@pytest.mark.parametrize(
    ("action", "start_status", "audit_action"),
    [
        ("check-in", "BOOKED", "appointment.check_in"),
        ("complete", "CHECKED_IN", "appointment.complete"),
        ("no-show", "BOOKED", "appointment.no_show"),
    ],
)
def returns_one_audit_entry_named_for_the_action_when_a_status_action_succeeds(
    action: str, start_status: str, audit_action: str
) -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, status=start_status)

    _post(_signed_in(_clinician_user(clinic)), appointment, action)

    entries = AuditLogEntry.objects.filter(entity_id=str(appointment.pk), action=audit_action)
    assert entries.count() == 1


def returns_row_lock_query_when_an_appointment_is_changed() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic)
    client = _signed_in(_admin())

    with CaptureQueriesContext(connection) as queries:
        _cancel(client, appointment)

    locking = [query for query in queries.captured_queries if "FOR UPDATE" in query["sql"]]
    assert any('"scheduling_appointment"' in query["sql"] for query in locking)


def returns_403_when_a_patient_uses_a_status_action_on_a_missing_appointment() -> None:
    clinic = make_clinic()
    missing = _make_appointment(clinic)
    missing_id = missing.pk
    missing.delete()
    client = _signed_in(clinic.patient)

    response = client.post(
        f"{APPOINTMENTS}/{missing_id}/check-in", {}, content_type="application/json"
    )

    assert response.status_code == 403


def returns_the_same_room_when_the_new_slot_overlaps_the_only_room_s_old_booking() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    room = make("Room", department=clinic.department)
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY, room=room)
    overlapping = NEXT_MONDAY + timedelta(minutes=15)

    response = _reschedule(_signed_in(clinic.patient), appointment, overlapping)

    appointment.refresh_from_db()
    assert response.status_code == 200
    assert appointment.room_id == room.pk


def returns_the_current_room_when_a_free_room_earlier_in_code_order_exists() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    make("Room", department=clinic.department, code="a-first")
    current = make("Room", department=clinic.department, code="b-current")
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY, room=current)

    response = _reschedule(_signed_in(clinic.patient), appointment, MONDAY_AFTER)

    appointment.refresh_from_db()
    assert response.status_code == 200
    assert appointment.room_id == current.pk
