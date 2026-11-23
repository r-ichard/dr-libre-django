"""Section 16: the seed_demo command, its guards, its accounts and its audit entry."""

import json
import re

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import CommandError
from django.utils import timezone

from scheduling.demo_seed.seed_support import DEMO_PASSWORD, row_counts, run_seed, seed_environment
from scheduling.models import AuditLogEntry, Hospital, User
from scheduling.models.builders import make

pytestmark = pytest.mark.django_db
# Never use transaction=True here: its teardown flush would TRUNCATE the audit table.

__all__ = ["seed_environment"]

ACCOUNT_ROLES = {
    "admin@example.test": "ADMIN",
    "clinician@example.test": "CLINICIAN",
    "patient@example.test": "PATIENT",
}
PASSWORDLESS_EMAIL = "passwordless@example.test"


def raises_command_error_and_writes_nothing_when_debug_is_off(
    seed_environment: None, settings: pytest.FixtureRequest
) -> None:
    setattr(settings, "DEBUG", False)  # noqa: B010
    before = row_counts()

    with pytest.raises(CommandError, match="DEBUG"):
        run_seed()

    assert row_counts() == before


@pytest.mark.parametrize("password", [None, ""])
def raises_error_and_writes_nothing_when_demo_password_is_missing_or_empty(
    seed_environment: None, monkeypatch: pytest.MonkeyPatch, password: str | None
) -> None:
    if password is None:
        monkeypatch.delenv("DEMO_PASSWORD")
    else:
        monkeypatch.setenv("DEMO_PASSWORD", password)
    before = row_counts()

    with pytest.raises((CommandError, ImproperlyConfigured), match="DEMO_PASSWORD"):
        run_seed()

    assert row_counts() == before


@pytest.mark.parametrize(("email", "role"), sorted(ACCOUNT_ROLES.items()))
def returns_true_when_demo_account_checks_the_environment_password(
    seed_environment: None, email: str, role: str
) -> None:
    run_seed()

    account = User.objects.get(email=email)

    assert account.role == role
    assert account.check_password(DEMO_PASSWORD) is True


def returns_false_when_another_password_is_checked(seed_environment: None) -> None:
    run_seed()

    account = User.objects.get(email="admin@example.test")

    assert account.check_password("not-the-demo-password") is False


def returns_unusable_password_and_verified_email_when_account_is_the_passwordless_patient(
    seed_environment: None,
) -> None:
    run_seed()

    account = User.objects.get(email=PASSWORDLESS_EMAIL)

    assert account.role == "PATIENT"
    assert account.has_usable_password() is False
    assert account.check_password(DEMO_PASSWORD) is False
    assert account.email_verified_at is not None


def returns_new_hash_only_when_password_in_environment_changed(
    seed_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_seed()
    version_after_first_run = User.objects.get(email="admin@example.test").version

    run_seed()
    assert User.objects.get(email="admin@example.test").version == version_after_first_run

    monkeypatch.setenv("DEMO_PASSWORD", "another-demo-password")
    run_seed()
    assert User.objects.get(email="admin@example.test").check_password("another-demo-password")


def returns_audit_entry_with_only_integer_counts_when_seeded(seed_environment: None) -> None:
    run_seed()

    entry = AuditLogEntry.objects.get(action="demo_seed.run")

    assert entry.action == "demo_seed.run"
    assert entry.actor_id is None
    assert set(entry.metadata) == {"ids", "counts", "statuses", "changed_fields", "email_domain"}
    expected_keys = {
        "hospital_count", "department_count", "specialty_count", "room_count",
        "appointmenttype_count", "user_count", "clinicianprofile_count",
        "availabilityrule_count", "timeoff_count", "appointment_count", "waitlistentry_count",
        "notification_count",
    }  # fmt: skip
    assert set(entry.metadata["counts"]) == expected_keys
    assert all(type(count) is int and count > 0 for count in entry.metadata["counts"].values())
    assert entry.metadata["ids"] == {}


def returns_no_seeded_name_email_or_phone_when_audit_metadata_is_serialised(
    seed_environment: None,
) -> None:
    run_seed()

    serialised = json.dumps(AuditLogEntry.objects.get(action="demo_seed.run").metadata)

    for person in User.objects.all():
        assert person.full_name not in serialised
        assert person.email not in serialised
    assert "@" not in serialised
    assert "+44" not in serialised


def returns_no_new_audit_entry_when_command_runs_again_on_one_day(seed_environment: None) -> None:
    run_seed()
    first_count = AuditLogEntry.objects.count()

    run_seed()

    assert AuditLogEntry.objects.count() == first_count
    assert AuditLogEntry.objects.filter(action="demo_seed.run").count() == 1


def returns_unchanged_manual_row_when_seed_runs_again(seed_environment: None) -> None:
    run_seed()
    make("Hospital", code="manual-hospital", name="Hand made")

    run_seed()

    assert Hospital.objects.get(code="manual-hospital").name == "Hand made"
    assert Hospital.objects.get(code="manual-hospital").version == 1


def returns_fresh_context_correlation_id_and_instant_when_seed_runs(seed_environment: None) -> None:
    before = timezone.now()

    run_seed()

    entry = AuditLogEntry.objects.get(action="demo_seed.run")
    assert re.fullmatch(r"[0-9a-f]{32}", entry.correlation_id)
    assert before <= entry.created_at <= timezone.now()
