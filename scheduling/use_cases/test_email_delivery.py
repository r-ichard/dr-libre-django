"""Section 7.6 and 11: delivery of one notification email; a failure leaves the row pending."""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

from scheduling.domain.request_context import RequestContext
from scheduling.models import Notification
from scheduling.models.builders import make
from scheduling.use_cases import email_delivery
from scheduling.use_cases.email_delivery import send_notification_email, send_pending_emails
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

CONTEXT = RequestContext(correlation_id="test", now=datetime(2030, 1, 7, 6, 0, tzinfo=UTC))
SIGN_IN_PATH = "/sign-in"


class BrokenMailBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise RuntimeError("backend bug")


def _pending(kind: str, title: str) -> Notification:
    row = make("Notification", kind=kind, title=title, email_pending=True)
    assert isinstance(row, Notification)
    return row


def returns_false_pending_and_logged_trace_when_the_mail_backend_raises_runtime_error(
    settings: object, caplog: pytest.LogCaptureFixture
) -> None:
    notification = _pending("SCHEDULE_CHANGED", "Appointment booked")
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {"BACKEND": f"{__name__}.BrokenMailBackend", "OPTIONS": {}}
    }

    with bind_request_context(CONTEXT), caplog.at_level(logging.WARNING):
        sent = send_notification_email(notification.pk)

    notification.refresh_from_db()
    assert sent is False
    assert notification.email_pending is True
    assert [record.exc_info is not None for record in caplog.records] == [True]
    assert vars(caplog.records[0])["notification_id"] == str(notification.pk)


def returns_false_pending_and_logged_trace_when_building_the_message_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    notification = _pending("SCHEDULE_CHANGED", "Appointment booked")

    def failing_builder(row: Notification) -> EmailMessage:
        raise LookupError("no hospital")

    monkeypatch.setattr(email_delivery, "_message_of", failing_builder)

    with bind_request_context(CONTEXT), caplog.at_level(logging.WARNING):
        sent = send_notification_email(notification.pk)

    notification.refresh_from_db()
    assert sent is False
    assert notification.email_pending is True
    assert [record.exc_info is not None for record in caplog.records] == [True]


def returns_other_rows_sent_when_one_pending_row_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = _pending("SCHEDULE_CHANGED", "Broken one")
    healthy = _pending("SCHEDULE_CHANGED", "Healthy one")
    original = email_delivery._message_of  # noqa: SLF001

    def fails_for_broken(row: Notification) -> EmailMessage:
        if row.pk == broken.pk:
            raise LookupError("no hospital")
        return original(row)

    monkeypatch.setattr(email_delivery, "_message_of", fails_for_broken)

    with bind_request_context(CONTEXT):
        sent = send_pending_emails(10)

    assert sent == 1
    assert [message.subject for message in mail.outbox] == ["Healthy one"]
    healthy.refresh_from_db()
    broken.refresh_from_db()
    assert (healthy.email_pending, broken.email_pending) == (False, True)


@pytest.mark.parametrize("kind", ["WAITLIST_OFFERED", "WAITLIST_BOOKED", "APPOINTMENT_REMINDER"])
def returns_email_with_title_and_sign_in_link_when_notification_has_no_appointment(
    kind: str,
) -> None:
    notification = _pending(kind, "A slot is free")

    with bind_request_context(CONTEXT):
        sent = send_notification_email(notification.pk)

    assert sent is True
    message = mail.outbox[0]
    assert message.subject == "A slot is free"
    assert message.to == [notification.recipient.email]
    assert SIGN_IN_PATH in message.body.splitlines()[-1]
    notification.refresh_from_db()
    assert notification.email_pending is False
