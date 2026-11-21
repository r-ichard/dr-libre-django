"""Shared planted clinic of the public search page tests."""

from __future__ import annotations

from datetime import UTC, datetime, time

from django.db.models import Model

from scheduling.models import ClinicianProfile
from scheduling.models.builders import add_clinician, make
from scheduling.models.organisation import AppointmentType

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
HOUR_OF_SLOTS = {"start_time": time(11, 0), "end_time": time(14, 0), "slot_step_minutes": 30}
FIRST_START = "2030-01-07T11:00:00Z"
PLANTED_EMAIL = "planted.clinician@example.org"
PLANTED_PHONE = "+49 555 PLANTED-PHONE"
PLANTED_BIRTH = "1971-02-03"
PLANTED_PATIENT = "Planted Patient Person"
PLANTED_REASON = "PLANTED-REASON-TEXT"


def plant_clinic() -> tuple[ClinicianProfile, AppointmentType]:
    hospital = make("Hospital", name="Riverside General", street_address="1 River Road")
    department = make("Department", hospital=hospital, name="Heart Clinic")
    appointment_type = make("AppointmentType", department=department, name="Check-up")
    if not isinstance(appointment_type, AppointmentType):
        raise TypeError("builder returned a different model")
    user = make(
        "User",
        role="CLINICIAN",
        full_name="Ada Lovelace",
        email=PLANTED_EMAIL,
        phone=PLANTED_PHONE,
        date_of_birth=datetime.fromisoformat(PLANTED_BIRTH).date(),
    )
    clinician = add_clinician(department, HOUR_OF_SLOTS, user=user)
    patient = make("User", role="PATIENT", full_name=PLANTED_PATIENT)
    make(
        "Appointment",
        patient=patient,
        clinician=clinician,
        appointment_type=appointment_type,
        patient_reason=PLANTED_REASON,
    )
    return clinician, appointment_type


def update_row(row: Model, **fields: object) -> None:
    """Planted rows can be a version behind the database; reload, then change."""
    row.refresh_from_db()
    for name, value in fields.items():
        setattr(row, name, value)
    row.save()
