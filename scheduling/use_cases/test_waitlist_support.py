"""Shared builders of the waitlist tests. The cancelled appointments belong to another patient
whose visit reason is planted, so a test can prove it never reaches a waitlist reader."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from django.db.models import F

from scheduling.models import Appointment, User, WaitlistEntry
from scheduling.models.builders import STARTS_AT, Clinic, make

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
SLOT = STARTS_AT
THIRTY_MINUTES = timedelta(minutes=30)
ONE_DAY = timedelta(days=1)
FOREIGN_REASON = "planted-foreign-reason-4417"


def _admin_user() -> User:
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    return admin


def _entry_for(clinic: Clinic, **overrides: object) -> WaitlistEntry:
    """A WAITING entry of the clinic's patient whose window holds SLOT."""
    fields = {
        "patient": clinic.patient,
        "appointment_type": clinic.appointment_type,
        "earliest_at": SLOT - ONE_DAY,
        "latest_at": SLOT + ONE_DAY,
    }
    row = make("WaitlistEntry", **{**fields, **overrides})
    assert isinstance(row, WaitlistEntry)
    return row


def _entry_aged(clinic: Clinic, age: timedelta) -> WaitlistEntry:
    """An entry of a new patient, created `age` before NOW."""
    patient = make("User")
    assert isinstance(patient, User)
    entry = _entry_for(clinic, patient=patient)
    WaitlistEntry.objects.filter(pk=entry.pk).update(created_at=NOW - age, version=F("version") + 1)
    entry.refresh_from_db()
    return entry


def _booked_slot(clinic: Clinic, starts_at: datetime = SLOT, **overrides: object) -> Appointment:
    """A BOOKED appointment of another patient with the planted reason."""
    fields = {
        "appointment_type": clinic.appointment_type,
        "clinician": clinic.clinician,
        "patient": make("User"),
        "starts_at": starts_at,
        "ends_at": starts_at + THIRTY_MINUTES,
        "patient_reason": FOREIGN_REASON,
    }
    row = make("Appointment", **{**fields, **overrides})
    assert isinstance(row, Appointment)
    return row


def _cancelled_slot(clinic: Clinic, starts_at: datetime = SLOT, **overrides: object) -> Appointment:
    return _booked_slot(
        clinic,
        starts_at,
        status="CANCELLED",
        cancelled_at=NOW,
        cancellation_reason="No longer needed",
        **overrides,
    )


def _offered_entry(clinic: Clinic, freed: Appointment, **overrides: object) -> WaitlistEntry:
    return _entry_for(clinic, status="OFFERED", offered_appointment=freed, **overrides)
