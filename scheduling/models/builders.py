"""Row builders for the schema tests. Models are looked up by name so a missing model fails
as a LookupError in the test that needs it, not as an import error for the whole suite."""

import itertools
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import pytest
from django.apps import apps
from django.contrib.auth.hashers import make_password
from django.db import DatabaseError, transaction
from django.db.models import Model

from scheduling.models.organisation import AppointmentType, Department
from scheduling.models.people import ClinicianProfile, User

STARTS_AT = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)
ENDS_AT = STARTS_AT + timedelta(minutes=30)
FAR_FUTURE = datetime(2031, 1, 1, tzinfo=UTC)
SIXTY_FOUR = "a" * 64
_counter = itertools.count(1)


def unique_text(prefix: str) -> str:
    return f"{prefix}-{next(_counter)}"


def unique_hash() -> str:
    return f"{next(_counter):064x}"


def model_class(model_name: str) -> type[Model]:
    return apps.get_model("scheduling", model_name)


def _hospital_defaults() -> dict[str, Callable[[], object]]:
    return {
        "name": lambda: "Riverside Hospital",
        "code": lambda: unique_text("hospital"),
        "description": lambda: "",
        "street_address": lambda: "1 River Road",
        "postal_code": lambda: "10115",
        "city": lambda: "Berlin",
        "country": lambda: "DE",
        "phone": lambda: "+49 30 1234",
        "time_zone": lambda: "Europe/Berlin",
        "is_active": lambda: True,
    }


def _clinician_defaults() -> dict[str, Callable[[], object]]:
    return {
        "user": lambda: make("User", role="CLINICIAN"),
        "department": lambda: make("Department"),
        "specialty": lambda: make("Specialty"),
        "title": lambda: "Dr",
        "bio": lambda: "",
    }


def _appointment_defaults() -> dict[str, Callable[[], object]]:
    return {
        "patient": lambda: make("User"),
        "clinician": lambda: make("ClinicianProfile"),
        "appointment_type": lambda: make("AppointmentType"),
        "starts_at": lambda: STARTS_AT,
        "ends_at": lambda: ENDS_AT,
        "status": lambda: "BOOKED",
        "source": lambda: "ONLINE",
        "patient_reason": lambda: "",
        "cancellation_reason": lambda: "",
    }


def _hold_defaults() -> dict[str, Callable[[], object]]:
    return {
        "clinician": lambda: make("ClinicianProfile"),
        "appointment_type": lambda: make("AppointmentType"),
        "starts_at": lambda: STARTS_AT,
        "ends_at": lambda: ENDS_AT,
        "source": lambda: "ONLINE",
        "visitor_name": lambda: "Ada Visitor",
        "visitor_birth_date": lambda: date(1990, 1, 1),
        "visitor_email": lambda: f"{unique_text('visitor')}@example.com",
        "visitor_phone": lambda: "+49 30 5555",
        "visitor_reason": lambda: "",
        "expires_at": lambda: FAR_FUTURE,
        "terms_accepted_at": lambda: STARTS_AT,
    }


def _verification_code_defaults() -> dict[str, Callable[[], object]]:
    return {
        "hold": lambda: make("BookingHold"),
        "code_hash": unique_hash,
        "email": lambda: f"{unique_text('code')}@example.com",
        "purpose": lambda: "BOOKING",
        "expires_at": lambda: FAR_FUTURE,
        "attempts_used": lambda: 0,
    }


def _defaults() -> dict[str, dict[str, Callable[[], object]]]:
    return {
        "Hospital": _hospital_defaults(),
        "Department": {
            "hospital": lambda: make("Hospital"),
            "name": lambda: "Cardiology",
            "code": lambda: unique_text("department"),
            "description": lambda: "",
        },
        "Specialty": {
            "name": lambda: "Cardiology",
            "code": lambda: unique_text("specialty"),
            "is_active": lambda: True,
        },
        "User": {
            "email": lambda: f"{unique_text('user')}@example.com",
            "password": lambda: make_password("correct horse battery staple"),
            "full_name": lambda: "Pat Example",
            "role": lambda: "PATIENT",
            "is_active": lambda: True,
            "phone": lambda: "",
        },
        "ClinicianProfile": _clinician_defaults(),
        "Room": {
            "department": lambda: make("Department"),
            "name": lambda: "Room one",
            "code": lambda: unique_text("room"),
            "floor": lambda: "1",
            "capacity": lambda: 1,
            "equipment": lambda: [],
            "is_active": lambda: True,
        },
        "AppointmentType": {
            "department": lambda: make("Department"),
            "name": lambda: "Check-up",
            "code": lambda: unique_text("type"),
            "duration_minutes": lambda: 30,
            "needs_room": lambda: False,
            "buffer_minutes": lambda: 0,
            "colour": lambda: "#336699",
            "is_active": lambda: True,
            "is_bookable_online": lambda: True,
        },
        "AvailabilityRule": {
            "clinician": lambda: make("ClinicianProfile"),
            "weekday": lambda: 1,
            "start_time": lambda: time(9, 0),
            "end_time": lambda: time(17, 0),
            "slot_step_minutes": lambda: 15,
            "valid_from": lambda: date(2030, 1, 1),
        },
        "TimeOff": {
            "clinician": lambda: make("ClinicianProfile"),
            "starts_at": lambda: STARTS_AT,
            "ends_at": lambda: ENDS_AT,
            "reason": lambda: "",
        },
        "Appointment": _appointment_defaults(),
        "ClinicalNote": {"appointment": lambda: make("Appointment"), "clinical_notes": lambda: ""},
        "WaitlistEntry": {
            "patient": lambda: make("User"),
            "appointment_type": lambda: make("AppointmentType"),
            "earliest_at": lambda: STARTS_AT,
            "latest_at": lambda: ENDS_AT,
            "status": lambda: "WAITING",
        },
        "Notification": {
            "recipient": lambda: make("User"),
            "kind": lambda: "SCHEDULE_CHANGED",
            "title": lambda: "Appointment booked",
            "body": lambda: "",
        },
        "AuditLogEntry": {
            "action": lambda: "appointment.booked",
            "entity_type": lambda: "Appointment",
            "entity_id": lambda: "entity-1",
            "metadata": lambda: {},
            "correlation_id": lambda: unique_text("correlation"),
        },
        "Session": {
            "user": lambda: make("User"),
            "token_hash": unique_hash,
            "opened_by": lambda: "PASSWORD",
            "expires_at": lambda: FAR_FUTURE,
            "user_agent": lambda: "",
        },
        "ApiClient": {
            "name": lambda: "Reporting service",
            "user": lambda: make("User"),
            "token_hash": unique_hash,
        },
        "SignInFailure": {"email_hash": unique_hash, "failed_at": lambda: STARTS_AT},
        "BookingHold": _hold_defaults(),
        "VerificationCode": _verification_code_defaults(),
        "SignInLink": {
            "token_hash": unique_hash,
            "patient": lambda: make("User"),
            "expires_at": lambda: FAR_FUTURE,
        },
    }


def make(model_name: str, **overrides: object) -> Model:
    factories = _defaults()[model_name]
    fields = {name: factory() for name, factory in factories.items() if name not in overrides}
    return model_class(model_name)._default_manager.create(**fields, **overrides)


def make_user(**overrides: object) -> User:
    return _typed(make("User", **overrides), User)


def refuses(model_name: str, **overrides: object) -> None:
    """The database, not Python validation, must reject the row."""
    with pytest.raises(DatabaseError), transaction.atomic():
        make(model_name, **overrides)


def field_of(row: Model, field_name: str) -> object:
    return getattr(row, field_name)


def change_and_save(row: Model, field_name: str, value: object) -> None:
    setattr(row, field_name, value)
    row.save()


@dataclass(frozen=True)
class Clinic:
    department: Department
    appointment_type: AppointmentType
    clinician: ClinicianProfile
    patient: User


def _typed[Row: Model](row: Model, kind: type[Row]) -> Row:
    if not isinstance(row, kind):
        raise TypeError(f"expected {kind.__name__}")
    return row


def make_clinic(
    type_fields: dict[str, object] | None = None, rule_fields: dict[str, object] | None = None
) -> Clinic:
    """One department with a bookable type, a clinician available Mondays and a patient."""
    department = _typed(make("Department"), Department)
    appointment_type = make("AppointmentType", department=department, **(type_fields or {}))
    clinician = add_clinician(department, rule_fields)
    return Clinic(
        department,
        _typed(appointment_type, AppointmentType),
        clinician,
        _typed(make("User"), User),
    )


def add_clinician(
    department: Model, rule_fields: dict[str, object] | None = None, **profile_fields: object
) -> ClinicianProfile:
    clinician = make("ClinicianProfile", department=department, **profile_fields)
    make("AvailabilityRule", clinician=clinician, **(rule_fields or {}))
    return _typed(clinician, ClinicianProfile)
