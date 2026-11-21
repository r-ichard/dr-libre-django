"""Section 7.3 and 12.2 use: a valid link signs the Patient in once, for 24 hours, no extension."""

from collections.abc import Iterator
from datetime import timedelta

import pytest

from scheduling.domain.failure import Success
from scheduling.domain.vocabulary import SessionKind
from scheduling.models import AuditLogEntry, Session, SignInLink
from scheduling.use_cases.session import resolve_session
from scheduling.use_cases.test_sign_in_link_support import (
    FIFTEEN_MINUTES,
    NOW,
    REFUSAL,
    _at,
    _patient,
    _stored_link,
    _use,
)

pytestmark = pytest.mark.django_db

TOKEN = "planted-token-abcdefghijklmnopqrstuvwxyz"  # noqa: S105 - a planted test value
ONE_SECOND = timedelta(seconds=1)


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with _at(NOW):
        yield


@pytest.mark.parametrize("has_password", [True, False])
def returns_session_of_kind_email_link_lasting_exactly_24_hours_when_link_is_valid(
    has_password: bool,
) -> None:
    patient = _patient()
    if not has_password:
        patient.set_unusable_password()
        patient.email_verified_at = NOW
        patient.save()
    _stored_link(TOKEN, patient)

    result = _use(TOKEN)

    assert isinstance(result, Success)
    session = Session.objects.get()
    assert session.opened_by == SessionKind.EMAIL_LINK
    assert session.expires_at == NOW + timedelta(hours=24)
    assert session.user_id == patient.pk
    assert SignInLink.objects.get().used_at == NOW


def returns_same_expiry_when_the_session_is_used_later() -> None:
    _stored_link(TOKEN, _patient())
    result = _use(TOKEN)
    assert isinstance(result, Success)

    with _at(NOW + timedelta(hours=23)):
        resolved = resolve_session(result.value.token)  # type: ignore[attr-defined]

    assert isinstance(resolved, Success)
    assert resolved.value.session.expires_at == NOW + timedelta(hours=24)


def returns_refusal_when_link_is_used_a_second_time() -> None:
    _stored_link(TOKEN, _patient())
    assert isinstance(_use(TOKEN), Success)

    assert _use(TOKEN) == REFUSAL
    assert Session.objects.count() == 1


def returns_same_refusal_when_link_is_unknown() -> None:
    _stored_link(TOKEN, _patient())

    assert _use("some-other-token-that-was-never-sent") == REFUSAL


def returns_link_usable_one_second_before_expiry() -> None:
    _stored_link(TOKEN, _patient())

    with _at(NOW + FIFTEEN_MINUTES - ONE_SECOND):
        assert isinstance(_use(TOKEN), Success)


@pytest.mark.parametrize(
    "state",
    ["expired", "used", "cancelled", "inactive", "became_admin"],
)
def returns_same_refusal_and_no_session_when_link_cannot_be_used(state: str) -> None:
    patient = _patient()
    overrides: dict[str, object] = {
        "used": {"used_at": NOW - ONE_SECOND},
        "cancelled": {"cancelled_at": NOW - ONE_SECOND},
    }.get(state, {})  # type: ignore[assignment]
    _stored_link(TOKEN, patient, **overrides)
    if state == "inactive":
        patient.is_active = False
        patient.save()
    if state == "became_admin":
        patient.role = "ADMIN"
        patient.save()
    moment = NOW + FIFTEEN_MINUTES if state == "expired" else NOW

    with _at(moment):
        result = _use(TOKEN)

    assert result == REFUSAL
    assert Session.objects.count() == 0


def returns_used_entry_with_patient_as_actor_and_domain_only_when_link_is_used() -> None:
    patient = _patient()
    _stored_link(TOKEN, patient)

    _use(TOKEN)

    entry = AuditLogEntry.objects.get(action="auth.link_used")
    assert entry.actor_id == patient.pk
    assert entry.metadata["email_domain"] == "example.test"
    assert TOKEN not in str(entry.metadata)


@pytest.mark.parametrize("token", [TOKEN, "never-sent-token"])
def returns_refused_entry_with_no_actor_when_link_is_refused(token: str) -> None:
    _stored_link(TOKEN, _patient(), used_at=NOW - ONE_SECOND)

    _use(token)

    entry = AuditLogEntry.objects.get(action="auth.link_refused")
    assert entry.actor_id is None
    assert token not in str(entry.metadata)
