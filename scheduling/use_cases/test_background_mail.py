"""The background send: after commit only, in the request context, failure logged blind."""

import json
import logging
from collections.abc import Sequence
from smtplib import SMTPException

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

from scheduling.use_cases.background_mail import send_after_commit, wait_until_idle
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.test_sign_in_link_support import (
    NOW,
    PATIENT_EMAIL,
    MailServerDownBackend,
    _at,
    _patient,
    _token_in_last_mail,
)
from scheduling.views.json_logging import JsonFormatter

pytestmark = pytest.mark.django_db

PLANTED_BODY = "planted-body-9f3a"
PLANTED_ADDRESS = "planted.person@example.test"
SEEN_CORRELATION_IDS: list[str] = []


class ContextRecordingBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        SEEN_CORRELATION_IDS.append(current_request_context().correlation_id)
        return len(email_messages)


def _message() -> EmailMessage:
    return EmailMessage("subject", PLANTED_BODY, "from@example.test", [PATIENT_EMAIL])


def _use_backend(settings: object, backend: type[BaseEmailBackend]) -> None:
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {"BACKEND": f"{backend.__module__}.{backend.__name__}", "OPTIONS": {}}
    }


def returns_no_mail_when_transaction_never_commits() -> None:
    send_after_commit(_message())
    wait_until_idle()

    assert mail.outbox == []


def returns_mail_after_commit_when_transaction_commits(
    django_capture_on_commit_callbacks: object,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        send_after_commit(_message())
    wait_until_idle()

    assert [sent.to for sent in mail.outbox] == [[PATIENT_EMAIL]]


def returns_request_correlation_id_inside_the_send_when_sent_in_background(
    django_capture_on_commit_callbacks: object, settings: object
) -> None:
    _use_backend(settings, ContextRecordingBackend)
    SEEN_CORRELATION_IDS.clear()

    with _at(NOW), django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        send_after_commit(_message())
    wait_until_idle()

    assert SEEN_CORRELATION_IDS == ["corr-link"]


def returns_log_line_without_body_or_address_when_mail_server_is_down(
    django_capture_on_commit_callbacks: object,
    settings: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _use_backend(settings, MailServerDownBackend)

    with caplog.at_level(logging.ERROR):
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            send_after_commit(_message())
        wait_until_idle()

    assert [record.getMessage() for record in caplog.records] == ["background mail not sent"]
    written = JsonFormatter().format(caplog.records[0])
    assert PLANTED_BODY not in written
    assert PATIENT_EMAIL not in written


class UnexpectedFailureBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise RuntimeError(f"{PATIENT_EMAIL} {PLANTED_BODY}")


def returns_log_line_without_body_or_address_when_send_raises_other_exception(
    django_capture_on_commit_callbacks: object,
    settings: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _use_backend(settings, UnexpectedFailureBackend)

    with caplog.at_level(logging.ERROR):
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            send_after_commit(_message())
        wait_until_idle()

    assert [record.getMessage() for record in caplog.records] == ["background mail not sent"]
    written = JsonFormatter().format(caplog.records[0])
    assert PLANTED_BODY not in written
    assert PATIENT_EMAIL not in written


def returns_link_address_with_only_the_token_when_link_is_mailed(
    django_capture_on_commit_callbacks: object, settings: object
) -> None:
    from scheduling.use_cases.sign_in_link import ask_for_link

    _patient()
    with _at(NOW), django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        ask_for_link(PATIENT_EMAIL, "203.0.113.7")
    wait_until_idle()

    expected = f"{settings.PUBLIC_BASE_URL}/sign-in/link?token={_token_in_last_mail()}"  # type: ignore[attr-defined]
    assert expected in str(mail.outbox[-1].body).splitlines()


class PlantedAddressSmtpFailureBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise SMTPException(f"rejected {PLANTED_ADDRESS}")


def returns_error_type_trace_and_correlation_id_in_log_when_send_fails(
    django_capture_on_commit_callbacks: object, settings: object
) -> None:
    _use_backend(settings, PlantedAddressSmtpFailureBackend)
    records: list[str] = []
    handler = logging.Handler()
    handler.setFormatter(JsonFormatter())
    handler.emit = lambda record: records.append(handler.format(record))  # type: ignore[method-assign]
    logging.getLogger("drlibre.mail").addHandler(handler)

    try:
        with _at(NOW), django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            send_after_commit(_message())
        wait_until_idle()
    finally:
        logging.getLogger("drlibre.mail").removeHandler(handler)

    line = json.loads(records[0])
    assert line["correlation_id"] == "corr-link"
    assert line["exception"]["type"] == "SMTPException"
    assert any("send_messages" in frame for frame in line["exception"]["frames"])
    assert PLANTED_ADDRESS not in records[0]
    assert PLANTED_BODY not in records[0]
