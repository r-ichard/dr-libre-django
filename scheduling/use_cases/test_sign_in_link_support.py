"""Shared builders of the sign-in link tests (task 13). The new modules are imported inside the
helpers, so a missing one fails the test that needs it and not the whole collection."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta

from django.core import mail
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

from scheduling.domain.failure import Failure, FieldMessage, Result
from scheduling.domain.request_context import RequestContext
from scheduling.models import SignInLink, User
from scheduling.models.builders import make
from scheduling.use_cases.request_context import bind_request_context

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
FIFTEEN_MINUTES = timedelta(minutes=15)
ADDRESS = "203.0.113.7"
PATIENT_EMAIL = "pat.patient@example.test"
TOKEN_PATTERN = re.compile(r"token=([A-Za-z0-9_-]+)")
REFUSAL = Failure.invalid_input(
    [FieldMessage("token", "This sign-in link has expired or was already used.")]
)

type Ask = Callable[..., Result[None]]


class MailServerDownBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise ConnectionRefusedError("mail server down")


def _at(instant: datetime) -> AbstractContextManager[None]:
    return bind_request_context(RequestContext("corr-link", instant))


def _patient(email: str = PATIENT_EMAIL, /, **overrides: object) -> User:
    patient = make("User", email=email, **overrides)
    assert isinstance(patient, User)
    return patient


def _token_in_last_mail() -> str:
    found = TOKEN_PATTERN.search(str(mail.outbox[-1].body))
    assert found is not None, mail.outbox[-1].body
    return found.group(1)


def _stored_link(token: str, patient: User, **overrides: object) -> SignInLink:
    """A link as the ask would have stored it: only the hash of the token."""
    from scheduling.use_cases.session import hash_token

    fields: dict[str, object] = {
        "token_hash": hash_token(token),
        "patient": patient,
        "created_at": NOW,
        "expires_at": NOW + FIFTEEN_MINUTES,
    }
    link = make("SignInLink", **{**fields, **overrides})
    assert isinstance(link, SignInLink)
    return link


def _use(token: str) -> Result[object]:
    from scheduling.use_cases.sign_in_link import use_link

    return use_link(token, "pytest-agent")
