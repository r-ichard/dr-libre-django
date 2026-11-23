"""Section 8: a patient edits phone and birth date; the audit names fields, not values."""

import json
from datetime import UTC, date, datetime

import pytest

from scheduling.domain.failure import Failure, FailureCode, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import AuditLogEntry, User
from scheduling.models.builders import make
from scheduling.use_cases.profile import ProfileCommand, update_profile
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 3, 15, 9, 0, tzinfo=UTC)
PHONE = "+33 1 23 45 67 89"
BORN = date(1990, 2, 28)


def _patient(**overrides: object) -> User:
    user = make("User", role="PATIENT", **overrides)
    assert isinstance(user, User)
    return user


def _update(user: User, phone: str, born: date | None) -> object:
    with bind_request_context(RequestContext(correlation_id="corr-1", now=NOW)):
        return update_profile(ProfileCommand(phone, born), user)


def _entries() -> list[AuditLogEntry]:
    return list(AuditLogEntry.objects.filter(action="profile.update"))


def returns_phone_stored_and_only_phone_audited_when_only_phone_changes() -> None:
    user = _patient()

    result = _update(user, PHONE, user.date_of_birth)

    user.refresh_from_db()
    assert isinstance(result, Success) and user.phone == PHONE
    assert [entry.metadata["changed_fields"] for entry in _entries()] == [["phone"]]


def returns_birth_date_stored_and_only_it_audited_when_only_birth_date_changes() -> None:
    user = _patient(phone="")

    _update(user, "", BORN)

    user.refresh_from_db()
    assert user.date_of_birth == BORN
    assert [entry.metadata["changed_fields"] for entry in _entries()] == [["date_of_birth"]]


def returns_cleared_phone_and_birth_date_when_input_is_empty() -> None:
    user = _patient(phone=PHONE, date_of_birth=BORN)

    _update(user, "", None)

    user.refresh_from_db()
    assert (user.phone, user.date_of_birth) == ("", None)


def returns_no_audit_entry_when_nothing_changed() -> None:
    user = _patient(phone=PHONE, date_of_birth=BORN)

    result = _update(user, PHONE, BORN)

    assert isinstance(result, Success) and _entries() == []


def returns_audit_metadata_without_phone_digits_or_birth_date() -> None:
    user = _patient()

    _update(user, "0123456789", BORN)

    text = json.dumps([entry.metadata for entry in _entries()])
    assert "0123456789" not in text and "1990" not in text


@pytest.mark.parametrize(
    ("phone", "born", "field"),
    [("12345", None, "phone"), ("", date(2030, 3, 16), "date_of_birth")],
)
def returns_invalid_input_and_changes_nothing_when_a_value_breaks_its_rule(
    phone: str, born: date | None, field: str
) -> None:
    user = _patient(phone="0987654321")

    result = _update(user, phone, born)

    user.refresh_from_db()
    assert isinstance(result, Failure) and result.code == FailureCode.INVALID_INPUT
    assert [item["field"] for item in result.details["fields"]] == [field]  # type: ignore[attr-defined]
    assert user.phone == "0987654321" and _entries() == []
