"""Section 11 notifications and section 7.6 emails of cancel and reschedule: what is mailed, when,
and what happens when the mail server is down. Driven through the API."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import timedelta
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.core.management import call_command
from django.db.models import F

from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, Notification
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases.email_delivery import send_notification_email, send_pending_emails
from scheduling.use_cases.request_context import bind_request_context
from scheduling.views import clock
from scheduling.views.appointment_action_support import (
    MONDAY_AFTER,
    NEXT_MONDAY,
    NOW,
    admin,
    cancel,
    make_appointment,
    reschedule,
    signed_in,
    status_of,
)

if TYPE_CHECKING:
    from django.core.mail import EmailMessage

pytestmark = pytest.mark.django_db

SENDER = "bookings@drlibre.example"
PLANTED_REASON = "planted-cancel-reason-7731"
PLANTED_VISIT_REASON = "planted-visit-reason-5521"
PLANTED_NOTE = "planted-clinical-note-9904"
OnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


class MailServerDownBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise ConnectionRefusedError("mail server down")


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


@pytest.fixture(autouse=True)
def sender_address(settings: object) -> None:
    settings.EMAIL_SENDER = SENDER  # type: ignore[attr-defined]


def _plant_free_text(appointment: Appointment) -> None:
    Appointment.objects.filter(pk=appointment.pk).update(
        version=F("version") + 1, patient_reason=PLANTED_VISIT_REASON, clinical_notes=PLANTED_NOTE
    )


def returns_one_email_with_local_time_and_names_after_commit_when_cancelling(
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    clinic = make_clinic()
    appointment = make_appointment(clinic)
    _plant_free_text(appointment)

    with django_capture_on_commit_callbacks(execute=True):
        cancel(signed_in(admin()), appointment, PLANTED_REASON)

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.from_email == SENDER
    assert message.to == [clinic.patient.email]
    assert "2030-01-07 at 11:00 (Europe/Berlin)" in message.body
    assert "Riverside Hospital" in message.body
    assert str(clinic.clinician.user.full_name) in message.body
    assert "/sign-in" in message.body
    assert "token" not in message.body.lower()


def returns_no_reason_or_note_in_any_email_when_cancelling_and_rescheduling(
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    clinic = make_clinic()
    appointment = make_appointment(clinic, starts_at=NEXT_MONDAY)
    _plant_free_text(appointment)
    client = signed_in(clinic.patient)

    with django_capture_on_commit_callbacks(execute=True):
        reschedule(client, appointment, MONDAY_AFTER)
        cancel(client, appointment, PLANTED_REASON)

    assert len(mail.outbox) == 2
    for message in mail.outbox:
        text = f"{message.subject}\n{message.body}"
        for planted in (PLANTED_REASON, PLANTED_VISIT_REASON, PLANTED_NOTE):
            assert planted not in text


def returns_no_email_and_no_notification_when_the_change_is_refused(
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    clinic = make_clinic()
    appointment = make_appointment(clinic, starts_at=NEXT_MONDAY)
    make_appointment(clinic, starts_at=MONDAY_AFTER, patient=make("User"))

    with django_capture_on_commit_callbacks(execute=True):
        response = reschedule(signed_in(clinic.patient), appointment, MONDAY_AFTER)

    assert response.status_code == 409
    assert mail.outbox == []
    assert Notification.objects.filter(appointment=appointment).count() == 0


def returns_pending_notification_and_kept_change_when_mail_server_is_down(
    settings: object, django_capture_on_commit_callbacks: OnCommit
) -> None:
    clinic = make_clinic()
    appointment = make_appointment(clinic)
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {"BACKEND": f"{__name__}.MailServerDownBackend", "OPTIONS": {}}
    }

    with django_capture_on_commit_callbacks(execute=True):
        response = cancel(signed_in(admin()), appointment)

    assert response.status_code == 200
    assert status_of(appointment) == "CANCELLED"
    assert Notification.objects.get(appointment=appointment).email_pending is True


def returns_one_email_when_pending_emails_are_retried_after_a_failed_send(
    settings: object, django_capture_on_commit_callbacks: OnCommit
) -> None:
    clinic = make_clinic()
    appointment = make_appointment(clinic)
    working_mailers = settings.MAILERS  # type: ignore[attr-defined]
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {"BACKEND": f"{__name__}.MailServerDownBackend", "OPTIONS": {}}
    }
    with django_capture_on_commit_callbacks(execute=True):
        cancel(signed_in(admin()), appointment)
    settings.MAILERS = working_mailers  # type: ignore[attr-defined]
    output = StringIO()

    call_command("send_pending_emails", stdout=output)
    call_command("send_pending_emails", stdout=output)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [clinic.patient.email]
    assert Notification.objects.get(appointment=appointment).email_pending is False
    assert output.getvalue().split() == ["1", "0"]


def returns_no_email_before_commit_and_one_after_when_cancelling(
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    clinic = make_clinic()
    appointment = make_appointment(clinic)
    client = signed_in(admin())

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        cancel(client, appointment)

    assert mail.outbox == []
    assert len(callbacks) == 1
    callbacks[0]()
    assert len(mail.outbox) == 1


def returns_false_and_sends_nothing_when_the_notification_was_already_emailed() -> None:
    clinic = make_clinic()
    appointment = make_appointment(clinic)
    cancel(signed_in(admin()), appointment)
    notification = Notification.objects.get(appointment=appointment)

    with bind_request_context(RequestContext(correlation_id="test", now=NOW)):
        assert send_notification_email(notification.pk) is True
        assert send_notification_email(notification.pk) is False
    assert len(mail.outbox) == 1


def returns_only_pending_notifications_within_the_limit_when_sending_in_batches() -> None:
    clinic = make_clinic()
    first = make_appointment(clinic, starts_at=NOW + timedelta(hours=48))
    second = make_appointment(clinic, starts_at=NOW + timedelta(hours=72))
    third = make_appointment(clinic, starts_at=NOW + timedelta(hours=96))
    admin_client = signed_in(admin())
    for appointment in (first, second, third):
        cancel(admin_client, appointment)
    Notification.objects.filter(appointment=first).update(
        email_pending=False, version=F("version") + 1
    )
    mail.outbox.clear()

    with bind_request_context(RequestContext(correlation_id="test", now=NOW)):
        assert send_pending_emails(1) == 1
        assert len(mail.outbox) == 1
        assert send_pending_emails(5) == 1
        assert len(mail.outbox) == 2
        assert send_pending_emails(5) == 0
