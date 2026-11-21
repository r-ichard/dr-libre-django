"""Shared arrangement for the demo seed tests."""

from datetime import UTC, datetime

import pytest
from django.core.management import call_command

from scheduling.models import (
    Appointment,
    AppointmentType,
    AuditLogEntry,
    AvailabilityRule,
    ClinicianProfile,
    Department,
    Hospital,
    Notification,
    Room,
    Specialty,
    TimeOff,
    User,
    WaitlistEntry,
)

DEMO_PASSWORD = "demo-password-for-tests"  # noqa: S105
FIXED_NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
SEEDED_MODELS = (
    Hospital, Department, Specialty, Room, AppointmentType, User, ClinicianProfile,
    AvailabilityRule, TimeOff, Appointment, WaitlistEntry, Notification,
)  # fmt: skip


@pytest.fixture
def seed_environment(monkeypatch: pytest.MonkeyPatch, settings: pytest.FixtureRequest) -> None:
    setattr(settings, "DEBUG", True)  # noqa: B010
    monkeypatch.setenv("DEMO_PASSWORD", DEMO_PASSWORD)


def run_seed() -> None:
    call_command("seed_demo")


def row_counts() -> dict[str, int]:
    counts = {model.__name__: model._default_manager.count() for model in SEEDED_MODELS}
    counts["AuditLogEntry"] = AuditLogEntry._default_manager.count()
    return counts
