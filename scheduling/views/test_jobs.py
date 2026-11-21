"""Section 14: POST /jobs/reminders, admin only."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from django.test import Client

from scheduling.models import AuditLogEntry, Notification
from scheduling.models.builders import make, make_clinic
from scheduling.views import clock
from scheduling.views.test_appointment_support import (
    NOW,
    THIRTY_MINUTES,
    _admin,
    _clinician_user,
    _signed_in,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

REMINDERS = "/api/v1/jobs/reminders"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _soon_appointment() -> None:
    clinic = make_clinic()
    starts_at = NOW + timedelta(hours=3)
    make(
        "Appointment",
        appointment_type=clinic.appointment_type,
        clinician=clinic.clinician,
        patient=clinic.patient,
        starts_at=starts_at,
        ends_at=starts_at + THIRTY_MINUTES,
    )


def _run(client: Client) -> _MonkeyPatchedWSGIResponse:
    return client.post(REMINDERS, {}, content_type="application/json")


def returns_401_when_running_reminders_without_session() -> None:
    assert _run(Client()).status_code == 401


def returns_403_when_patient_runs_reminders() -> None:
    clinic = make_clinic()

    response = _run(_signed_in(clinic.patient))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def returns_403_when_clinician_runs_reminders() -> None:
    clinic = make_clinic()

    assert _run(_signed_in(_clinician_user(clinic))).status_code == 403


def returns_reminder_count_when_admin_runs_reminders() -> None:
    _soon_appointment()
    _soon_appointment()

    response = _run(_signed_in(_admin()))

    assert response.status_code == 200
    assert response.json() == {"reminder_count": 2}
    assert Notification.objects.filter(kind="APPOINTMENT_REMINDER").count() == 2


def returns_zero_when_admin_runs_reminders_twice() -> None:
    _soon_appointment()
    client = _signed_in(_admin())

    _run(client)
    second = _run(client)

    assert second.json() == {"reminder_count": 0}
    assert Notification.objects.filter(kind="APPOINTMENT_REMINDER").count() == 1


def returns_audit_entry_with_the_admin_as_actor_when_reminders_created() -> None:
    _soon_appointment()
    user = _admin()

    _run(_signed_in(user))

    audit = AuditLogEntry.objects.get(action="reminder.run")
    assert audit.actor_id == user.pk
    assert audit.metadata["counts"] == {"reminder_count": 1}


def returns_400_when_reminders_body_has_a_field() -> None:
    response = _signed_in(_admin()).post(REMINDERS, {"hours": 48}, content_type="application/json")

    assert response.status_code == 400
