"""Section 3.1 visit reason on POST /appointments, and a booking whose email fails after commit."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.db import DatabaseError
from django.test import Client

from scheduling.models import Appointment, AuditLogEntry, Notification, User
from scheduling.models.builders import STARTS_AT, Clinic, add_clinician, make, make_clinic
from scheduling.use_cases import notifications
from scheduling.views import clock
from scheduling.views.appointment_action_support import (
    APPOINTMENTS,
    NOW,
    THIRTY_MINUTES,
    admin,
    clinician_user,
    make_appointment,
    signed_in,
)

if TYPE_CHECKING:
    from django.core.mail import EmailMessage
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

PLANTED_VISIT_REASON = "planted-visit-reason-5521"
OnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _book(client: Client, body: Mapping[str, object]) -> _MonkeyPatchedWSGIResponse:
    return client.post(APPOINTMENTS, body, content_type="application/json")


def _booking_body(clinic: Clinic, **extra: object) -> dict[str, object]:
    return {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "starts_at": "2030-01-07T10:00:00Z",
        **extra,
    }


def returns_201_and_reason_when_patient_books_with_reason() -> None:
    clinic = make_clinic()

    response = _book(signed_in(clinic.patient), _booking_body(clinic, reason="knee pain"))

    assert response.status_code == 201
    assert response.json()["reason"] == "knee pain"
    assert Appointment.objects.get().patient_reason == "knee pain"


def returns_empty_reason_when_booking_without_one() -> None:
    clinic = make_clinic()

    response = _book(signed_in(clinic.patient), _booking_body(clinic))

    assert response.status_code == 201
    assert response.json()["reason"] == ""


def returns_201_when_reason_is_200_characters() -> None:
    clinic = make_clinic()

    response = _book(signed_in(clinic.patient), _booking_body(clinic, reason="a" * 200))

    assert response.status_code == 201
    assert response.json()["reason"] == "a" * 200


def returns_201_and_empty_reason_when_reason_is_an_empty_string() -> None:
    clinic = make_clinic()

    response = _book(signed_in(clinic.patient), _booking_body(clinic, reason=""))

    assert response.status_code == 201
    assert response.json()["reason"] == ""


def returns_400_invalid_input_when_reason_is_201_characters() -> None:
    clinic = make_clinic()

    response = _book(signed_in(clinic.patient), _booking_body(clinic, reason="a" * 201))

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert [item["field"] for item in error["details"]["fields"]] == ["reason"]
    assert Appointment.objects.count() == 0


def returns_no_reason_in_audit_notification_email_or_log_when_booking_with_reason(
    django_capture_on_commit_callbacks: OnCommit, caplog: pytest.LogCaptureFixture
) -> None:
    clinic = make_clinic()
    client = signed_in(clinic.patient)
    body = _booking_body(clinic, reason=PLANTED_VISIT_REASON)

    with caplog.at_level(logging.DEBUG), django_capture_on_commit_callbacks(execute=True):
        response = _book(client, body)

    assert response.status_code == 201
    stored = [entry.metadata for entry in AuditLogEntry.objects.all()]
    stored += [(note.title, note.body) for note in Notification.objects.all()]
    stored += [(message.subject, message.body) for message in mail.outbox]
    stored += [record.getMessage() for record in caplog.records]
    stored += [vars(record) for record in caplog.records]
    assert Notification.objects.count() == 1
    assert PLANTED_VISIT_REASON not in str(stored)


def returns_reason_to_patient_clinician_and_admin_only() -> None:
    clinic = make_clinic()
    make_appointment(clinic, patient_reason=PLANTED_VISIT_REASON)
    other_clinician = add_clinician(clinic.department).user
    assert isinstance(other_clinician, User)
    other_clinician.refresh_from_db()

    allowed = [signed_in(clinic.patient), signed_in(clinician_user(clinic)), signed_in(admin())]
    shown = [
        [item["reason"] for item in client.get(APPOINTMENTS).json()["results"]]
        for client in allowed
    ]
    stranger = make("User")
    assert isinstance(stranger, User)
    outsiders = [signed_in(stranger), signed_in(other_clinician)]

    assert shown == [[PLANTED_VISIT_REASON]] * 3
    for outsider in outsiders:
        assert outsider.get(APPOINTMENTS).json()["results"] == []


def returns_reason_unchanged_when_appointment_is_rescheduled() -> None:
    clinic = make_clinic()
    original_start = STARTS_AT + timedelta(days=7)
    appointment = make_appointment(
        clinic,
        patient_reason=PLANTED_VISIT_REASON,
        starts_at=original_start,
        ends_at=original_start + THIRTY_MINUTES,
    )
    moved_to = STARTS_AT + timedelta(days=14)

    response = signed_in(clinic.patient).post(
        f"{APPOINTMENTS}/{appointment.pk}/reschedule",
        {"starts_at": moved_to.isoformat()},
        content_type="application/json",
    )

    appointment.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["reason"] == PLANTED_VISIT_REASON
    assert appointment.patient_reason == PLANTED_VISIT_REASON


class BrokenMailBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise RuntimeError("backend bug")


def returns_201_pending_notification_and_logged_trace_when_mail_backend_raises_runtime_error(
    settings: object,
    django_capture_on_commit_callbacks: OnCommit,
    caplog: pytest.LogCaptureFixture,
) -> None:
    clinic = make_clinic()
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {"BACKEND": f"{__name__}.BrokenMailBackend", "OPTIONS": {}}
    }
    body = _booking_body(clinic, reason=PLANTED_VISIT_REASON)

    with caplog.at_level(logging.WARNING), django_capture_on_commit_callbacks(execute=True):
        response = _book(signed_in(clinic.patient), body)

    assert response.status_code == 201
    assert Notification.objects.get().email_pending is True
    traced = [record for record in caplog.records if record.exc_info is not None]
    assert len(traced) == 1
    assert PLANTED_VISIT_REASON not in str(vars(traced[0]))


def returns_201_and_logged_trace_when_the_send_lookup_fails_after_commit(
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: OnCommit,
    caplog: pytest.LogCaptureFixture,
) -> None:
    clinic = make_clinic()

    def broken_lookup(identifier: object) -> bool:
        raise DatabaseError("lock failed")

    monkeypatch.setattr(notifications, "send_notification_email", broken_lookup)

    with caplog.at_level(logging.WARNING), django_capture_on_commit_callbacks(execute=True):
        response = _book(signed_in(clinic.patient), _booking_body(clinic))

    assert response.status_code == 201
    assert Notification.objects.get().email_pending is True
    assert [record for record in caplog.records if record.exc_info is not None]
