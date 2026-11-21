"""A mail backend that waits until released, to prove the request does not wait for the send."""

from collections.abc import Sequence
from threading import Event

from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

RELEASE = Event()
SENT: list[list[str]] = []


class BlockingBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        RELEASE.wait(timeout=10)
        SENT.extend(list(message.to) for message in email_messages)
        return len(email_messages)
