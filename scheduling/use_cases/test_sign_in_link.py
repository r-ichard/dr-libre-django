"""Section 7.3 ask: a link for an active Patient, the same answer for everyone else."""

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterator
from datetime import timedelta

import pytest
from django.core import mail
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.domain.failure import Failure, Success
from scheduling.models import AuditLogEntry, SignInLink, User
from scheduling.use_cases.test_sign_in_link_support import (
    ADDRESS,
    FIFTEEN_MINUTES,
    NOW,
    PATIENT_EMAIL,
    REFUSAL,
    Ask,
    MailServerDownBackend,
    _at,
    _patient,
    _token_in_last_mail,
    _use,
)

pytestmark = pytest.mark.django_db

NOT_PATIENTS = [
    {"role": "ADMIN"},
    {"role": "CLINICIAN"},
    {"role": "PATIENT", "is_active": False},
]
STATEMENT_PATTERN = re.compile(r'(INSERT INTO|UPDATE|FROM|SAVEPOINT|RELEASE|SELECT) ?"?(\w+)?')


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with _at(NOW):
        yield


def _statement_kinds(queries: list[dict[str, str]]) -> Counter[tuple[str, str]]:
    kinds = (STATEMENT_PATTERN.search(query["sql"]) for query in queries)
    # A savepoint name is unique per statement, so only its kind is counted.
    return Counter(
        (found.group(1), "" if found.group(1) == "SAVEPOINT" else found.group(2) or "")
        for found in kinds
        if found
    )


def returns_one_link_and_one_mail_when_email_is_active_patient(ask: Ask) -> None:
    patient = _patient()

    result = ask()

    assert result == Success(None)
    link = SignInLink.objects.get()
    assert (link.patient_id, link.expires_at, link.used_at) == (
        patient.pk,
        NOW + FIFTEEN_MINUTES,
        None,
    )
    assert [message.to for message in mail.outbox] == [[PATIENT_EMAIL]]


def returns_only_the_hash_of_the_mailed_token_when_link_is_stored(ask: Ask) -> None:
    _patient()

    ask()

    token = _token_in_last_mail()
    stored = SignInLink.objects.get()
    assert len(token) >= 22
    assert stored.token_hash != token
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in json.dumps(list(SignInLink.objects.values()), default=str)


def returns_link_that_signs_in_when_mailed_token_is_used(ask: Ask) -> None:
    patient = _patient()
    ask()

    result = _use(_token_in_last_mail())

    assert isinstance(result, Success)
    assert result.value.session.user_id == patient.pk  # type: ignore[attr-defined]


@pytest.mark.parametrize("fields", NOT_PATIENTS)
def returns_same_success_and_creates_nothing_when_email_is_not_an_active_patient(
    ask: Ask, fields: dict[str, object]
) -> None:
    _patient(**fields)
    users_before = User.objects.count()

    result = ask()

    assert result == Success(None)
    assert (SignInLink.objects.count(), len(mail.outbox), User.objects.count()) == (
        0,
        0,
        users_before,
    )


def returns_same_success_and_creates_nothing_when_email_is_unknown(ask: Ask) -> None:
    result = ask("nobody@example.test")

    assert result == Success(None)
    assert (SignInLink.objects.count(), len(mail.outbox), User.objects.count()) == (0, 0, 0)


def returns_patient_found_when_email_differs_in_case_and_spaces(ask: Ask) -> None:
    _patient()

    ask("  Pat.Patient@EXAMPLE.test ")

    assert SignInLink.objects.count() == 1


def returns_earlier_link_refused_when_asking_again(ask: Ask) -> None:
    _patient()
    ask()
    first_token = _token_in_last_mail()

    with _at(NOW + timedelta(minutes=1)):
        ask()

    first = SignInLink.objects.get(token_hash=hashlib.sha256(first_token.encode()).hexdigest())
    assert first.cancelled_at == NOW + timedelta(minutes=1)
    assert _use(first_token) == REFUSAL
    assert isinstance(_use(_token_in_last_mail()), Success)


def returns_rate_limited_on_fourth_ask_in_an_hour_for_one_email(ask: Ask) -> None:
    _patient()
    for _ in range(3):
        assert ask() == Success(None)

    assert ask() == Failure.rate_limited()
    assert SignInLink.objects.count() == 3


def returns_rate_limited_on_fourth_ask_when_email_is_unknown(ask: Ask) -> None:
    for _ in range(3):
        assert ask("nobody@example.test") == Success(None)

    assert ask("nobody@example.test") == Failure.rate_limited()


def returns_success_again_when_an_hour_has_passed_since_three_asks(ask: Ask) -> None:
    _patient()
    for _ in range(3):
        ask()

    with _at(NOW + timedelta(hours=1, seconds=1)):
        assert ask() == Success(None)


def returns_rate_limited_on_eleventh_ask_from_one_network_address(ask: Ask) -> None:
    for number in range(10):
        assert ask(f"user{number}@example.test", ADDRESS) == Success(None)

    assert ask("user10@example.test", ADDRESS) == Failure.rate_limited()
    assert ask("user10@example.test", "198.51.100.9") == Success(None)


def returns_same_success_when_mail_sending_fails(
    ask: Ask, settings: object, caplog: pytest.LogCaptureFixture
) -> None:
    _patient()
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {
            "BACKEND": f"{MailServerDownBackend.__module__}.MailServerDownBackend",
            "OPTIONS": {},
        }
    }

    result = ask()

    assert result == Success(None)
    assert PATIENT_EMAIL not in caplog.text
    assert "pat.patient" not in caplog.text


def returns_before_mail_is_sent_when_mail_backend_blocks(
    django_capture_on_commit_callbacks: object, settings: object
) -> None:
    from scheduling.use_cases.background_mail import wait_until_idle
    from scheduling.use_cases.sign_in_link import ask_for_link
    from scheduling.use_cases.test_blocking_backend import RELEASE, SENT

    _patient()
    RELEASE.clear()
    SENT.clear()
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {
            "BACKEND": "scheduling.use_cases.test_blocking_backend.BlockingBackend",
            "OPTIONS": {},
        }
    }

    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        result = ask_for_link(PATIENT_EMAIL, ADDRESS)
    sent_while_blocked = list(SENT)
    RELEASE.set()
    wait_until_idle()

    assert result == Success(None)
    assert sent_while_blocked == []
    assert SENT == [[PATIENT_EMAIL]]


def returns_one_insert_of_the_link_as_only_difference_when_patient_and_stranger_ask(
    ask: Ask,
) -> None:
    _patient()
    with CaptureQueriesContext(connection) as stranger:
        ask("nobody@example.test")
    with CaptureQueriesContext(connection) as patient:
        ask()

    extra = _statement_kinds(patient.captured_queries) - _statement_kinds(stranger.captured_queries)
    missing = _statement_kinds(stranger.captured_queries) - _statement_kinds(
        patient.captured_queries
    )
    assert extra == Counter({("INSERT INTO", "scheduling_signinlink"): 1})
    assert missing == Counter()


@pytest.mark.parametrize("email", [PATIENT_EMAIL, "nobody@example.test"])
def returns_one_requested_entry_with_domain_only_and_no_actor_when_link_is_asked(
    ask: Ask, email: str
) -> None:
    _patient()

    ask(email)

    entry = AuditLogEntry.objects.get(action="auth.link_requested")
    assert entry.actor_id is None
    assert entry.entity_type == "SignInLink"
    assert entry.metadata["email_domain"] == "example.test"
    assert "pat" not in json.dumps(entry.metadata)
    assert "nobody" not in json.dumps(entry.metadata)


def returns_refused_entry_with_no_actor_when_ask_is_rate_limited(ask: Ask) -> None:
    for _ in range(3):
        ask("nobody@example.test")

    ask("nobody@example.test")

    entry = AuditLogEntry.objects.get(action="auth.link_refused")
    assert entry.actor_id is None
    assert entry.metadata["email_domain"] == "example.test"


def returns_invalid_input_and_nothing_when_email_is_malformed(ask: Ask) -> None:
    result = ask("not-an-email")

    assert isinstance(result, Failure)
    assert result.code.value == "invalid_input"
    assert (SignInLink.objects.count(), AuditLogEntry.objects.count()) == (0, 0)
