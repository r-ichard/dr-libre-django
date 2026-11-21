"""Section 12.2: lifetime by kind and role, and the extension rule, as pure functions of now."""

from datetime import UTC, datetime, timedelta

import pytest

from scheduling.domain.session_rules import extended_expiry, session_lifetime
from scheduling.domain.vocabulary import Role, SessionKind

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def returns_twelve_hours_when_admin_opens_password_session() -> None:
    assert session_lifetime(SessionKind.PASSWORD, Role.ADMIN) == timedelta(hours=12)


@pytest.mark.parametrize("role", [Role.CLINICIAN, Role.PATIENT])
def returns_seven_days_when_clinician_or_patient_opens_password_session(role: Role) -> None:
    assert session_lifetime(SessionKind.PASSWORD, role) == timedelta(days=7)


@pytest.mark.parametrize("kind", [SessionKind.EMAIL_LINK, SessionKind.BOOKING_CODE])
@pytest.mark.parametrize("role", list(Role))
def returns_twenty_four_hours_when_session_opened_by_link_or_code(
    kind: SessionKind, role: Role
) -> None:
    assert session_lifetime(kind, role) == timedelta(hours=24)


def returns_new_expiry_when_less_than_half_remains() -> None:
    expires_at = NOW + timedelta(days=3, hours=11, minutes=59)

    assert extended_expiry(SessionKind.PASSWORD, Role.PATIENT, expires_at, NOW) == NOW + timedelta(
        days=7
    )


def returns_no_change_when_exactly_half_remains() -> None:
    expires_at = NOW + timedelta(hours=6)

    assert extended_expiry(SessionKind.PASSWORD, Role.ADMIN, expires_at, NOW) is None


def returns_no_change_when_more_than_half_remains() -> None:
    expires_at = NOW + timedelta(hours=11)

    assert extended_expiry(SessionKind.PASSWORD, Role.ADMIN, expires_at, NOW) is None


@pytest.mark.parametrize("kind", [SessionKind.EMAIL_LINK, SessionKind.BOOKING_CODE])
def returns_no_change_when_session_opened_by_link_or_code(kind: SessionKind) -> None:
    expires_at = NOW + timedelta(minutes=1)

    assert extended_expiry(kind, Role.PATIENT, expires_at, NOW) is None
