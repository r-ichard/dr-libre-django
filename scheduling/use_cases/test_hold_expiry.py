"""Section 7.1 and 7.7: an expired hold frees its slot, and a job of the worker removes it."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command
from django.db.models import F

from scheduling.models import AuditLogEntry, BookingHold
from scheduling.models.access import VerificationCode
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases.test_booking_support import NOW, VISITOR_EMAIL, _at, _held

pytestmark = pytest.mark.django_db

ONE_SECOND = timedelta(seconds=1)
TEN_MINUTES = timedelta(minutes=10)
LONG_AGO = datetime(2000, 1, 1, tzinfo=UTC)
TEN_MINUTES_LESS_ONE_SECOND = timedelta(minutes=10) - ONE_SECOND


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with _at(NOW):
        yield


def _expire_all() -> int:
    from scheduling.use_cases.hold_expiry import expire_booking_holds

    return expire_booking_holds()


def returns_expired_holds_and_codes_removed_with_one_audit_each() -> None:
    first = _held(make_clinic(), email="first.visitor@clinic-mail.test")
    second = _held(make_clinic(), email="second.visitor@clinic-mail.test")

    with _at(NOW + timedelta(minutes=10)):
        removed = _expire_all()

    assert removed == 2
    assert BookingHold.objects.count() == 0
    assert VerificationCode.objects.count() == 0
    entries = AuditLogEntry.objects.filter(action="booking_hold.expired")
    assert {entry.entity_id for entry in entries} == {str(first.pk), str(second.pk)}
    for entry in entries:
        assert entry.actor_id is None
        assert entry.metadata["email_domain"] == "clinic-mail.test"
        assert "visitor" not in str(entry.metadata)


def returns_live_hold_kept_when_it_expires_one_second_from_now() -> None:
    hold = _held(make_clinic())

    with _at(NOW + TEN_MINUTES_LESS_ONE_SECOND):
        removed = _expire_all()

    assert removed == 0
    assert BookingHold.objects.filter(pk=hold.pk).exists()
    assert AuditLogEntry.objects.filter(action="booking_hold.expired").count() == 0


def returns_hold_without_code_removed_when_it_expired() -> None:
    clinic = make_clinic()
    make(
        "BookingHold",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        visitor_email=VISITOR_EMAIL,
        expires_at=NOW - ONE_SECOND,
    )

    assert _expire_all() == 1
    assert BookingHold.objects.count() == 0


def returns_count_of_removed_holds_when_management_command_runs(capsys: object) -> None:
    _held(make_clinic())
    # The command reads the real clock, so the hold is moved to a fixed date long before it.
    long_ago = LONG_AGO
    BookingHold.objects.update(
        created_at=long_ago - TEN_MINUTES, expires_at=long_ago, version=F("version") + 1
    )

    call_command("expire_booking_holds")

    assert BookingHold.objects.count() == 0
    assert "1" in capsys.readouterr().out  # type: ignore[attr-defined]
