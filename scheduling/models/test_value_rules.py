"""Every stored-value rule of section 3: the illegal row is refused, the nearest legal one kept."""

from datetime import date, time, timedelta

import pytest
from django.contrib.auth.hashers import make_password

from scheduling.models.builders import (
    ENDS_AT,
    FAR_FUTURE,
    SIXTY_FOUR,
    STARTS_AT,
    field_of,
    make,
    model_class,
    refuses,
)

pytestmark = pytest.mark.django_db

ONE_MINUTE = timedelta(minutes=1)
UNUSABLE = make_password(None)
VERIFIED = {"email_verified_at": STARTS_AT}
PATIENT_WITHOUT_PASSWORD = {"role": "PATIENT", "password": UNUSABLE}

ILLEGAL_ROWS = [
    ("Hospital", {"name": ""}, "blank_hospital_name"),
    ("Hospital", {"code": ""}, "blank_hospital_code"),
    ("Hospital", {"latitude": 90.1, "longitude": 0}, "latitude_above_90"),
    ("Hospital", {"latitude": -90.1, "longitude": 0}, "latitude_below_minus_90"),
    ("Hospital", {"latitude": 0, "longitude": 180.1}, "longitude_above_180"),
    ("Hospital", {"latitude": 0, "longitude": -180.1}, "longitude_below_minus_180"),
    ("Hospital", {"latitude": 10, "longitude": None}, "latitude_without_longitude"),
    ("Hospital", {"latitude": None, "longitude": 10}, "longitude_without_latitude"),
    ("Department", {"name": ""}, "blank_department_name"),
    ("Department", {"code": ""}, "blank_department_code"),
    ("Specialty", {"name": ""}, "blank_specialty_name"),
    ("Specialty", {"code": ""}, "blank_specialty_code"),
    ("User", {"email": "Mixed@Example.com"}, "mixed_case_email"),
    ("User", {"email": ""}, "blank_email"),
    ("User", {"full_name": ""}, "blank_full_name"),
    ("User", {"role": "SUPERUSER"}, "unknown_role"),
    ("User", {**PATIENT_WITHOUT_PASSWORD, "email_verified_at": None}, "unverified_passwordless"),
    ("User", {"role": "CLINICIAN", "password": UNUSABLE, **VERIFIED}, "passwordless_clinician"),
    ("User", {"role": "ADMIN", "password": UNUSABLE, **VERIFIED}, "passwordless_admin"),
    ("ClinicianProfile", {"round_robin_weight": 0}, "round_robin_weight_zero"),
    ("Room", {"capacity": 0}, "room_capacity_zero"),
    ("Room", {"name": ""}, "blank_room_name"),
    ("Room", {"code": ""}, "blank_room_code"),
    ("AppointmentType", {"duration_minutes": 0}, "duration_zero"),
    ("AppointmentType", {"buffer_minutes": -1}, "buffer_negative"),
    ("AppointmentType", {"colour": "red"}, "colour_name"),
    ("AppointmentType", {"colour": "#FFFFFF"}, "colour_upper_case"),
    ("AppointmentType", {"colour": "#00ff7"}, "colour_five_digits"),
    ("AppointmentType", {"name": ""}, "blank_type_name"),
    ("AppointmentType", {"code": ""}, "blank_type_code"),
    ("AvailabilityRule", {"weekday": -1}, "weekday_minus_one"),
    ("AvailabilityRule", {"weekday": 7}, "weekday_seven"),
    ("AvailabilityRule", {"slot_step_minutes": 4}, "slot_step_four"),
    ("AvailabilityRule", {"slot_step_minutes": 241}, "slot_step_241"),
    ("AvailabilityRule", {"start_time": time(9), "end_time": time(9)}, "rule_ends_at_start"),
    ("AvailabilityRule", {"start_time": time(9, 0, 30)}, "start_time_with_seconds"),
    ("AvailabilityRule", {"end_time": time(17, 0, 30)}, "end_time_with_seconds"),
    ("AvailabilityRule", {"valid_to": date(2029, 12, 31)}, "valid_to_before_valid_from"),
    ("TimeOff", {"ends_at": STARTS_AT}, "time_off_ends_at_start"),
    ("TimeOff", {"reason": "x" * 201}, "time_off_reason_201_characters"),
    ("Appointment", {"ends_at": STARTS_AT}, "appointment_ends_at_start"),
    ("Appointment", {"ends_at": STARTS_AT - ONE_MINUTE}, "appointment_ends_before_start"),
    ("Appointment", {"clinical_notes": "x" * 5001}, "notes_5001_characters"),
    ("Appointment", {"status": "UNKNOWN"}, "unknown_appointment_status"),
    ("Appointment", {"source": "PHONE"}, "unknown_appointment_source"),
    ("Appointment", {"status": "CANCELLED"}, "cancelled_without_time_and_reason"),
    (
        "Appointment",
        {"status": "CANCELLED", "cancelled_at": STARTS_AT, "cancellation_reason": ""},
        "cancelled_without_reason",
    ),
    ("Appointment", {"cancelled_at": STARTS_AT}, "booked_with_cancellation_time"),
    ("Appointment", {"cancellation_reason": "changed mind"}, "booked_with_cancellation_reason"),
    ("WaitlistEntry", {"latest_at": STARTS_AT}, "waitlist_window_empty"),
    ("WaitlistEntry", {"status": "DONE"}, "unknown_waitlist_status"),
    ("WaitlistEntry", {"status": "OFFERED"}, "offered_without_appointment"),
    ("Notification", {"kind": "NEWSLETTER"}, "unknown_notification_kind"),
    ("Notification", {"title": ""}, "blank_notification_title"),
    ("AuditLogEntry", {"action": ""}, "blank_audit_action"),
    ("AuditLogEntry", {"entity_type": ""}, "blank_audit_entity_type"),
    ("AuditLogEntry", {"entity_id": ""}, "blank_audit_entity_id"),
    ("AuditLogEntry", {"correlation_id": ""}, "blank_audit_correlation_id"),
    ("Session", {"token_hash": "a" * 63}, "session_hash_63_characters"),
    ("Session", {"token_hash": "a" * 65}, "session_hash_65_characters"),
    ("Session", {"expires_at": STARTS_AT - timedelta(days=4000)}, "session_expired_at_creation"),
    ("BookingHold", {"ends_at": STARTS_AT}, "hold_ends_at_start"),
    ("BookingHold", {"expires_at": STARTS_AT - timedelta(days=4000)}, "hold_expired_at_creation"),
    ("BookingHold", {"visitor_email": "Mixed@Example.com"}, "hold_mixed_case_email"),
    ("BookingHold", {"source": "STAFF"}, "hold_source_staff"),
    ("VerificationCode", {"code_hash": "a" * 63}, "code_hash_63_characters"),
    ("VerificationCode", {"email": "Mixed@Example.com"}, "code_mixed_case_email"),
    ("VerificationCode", {"purpose": "LOGIN"}, "unknown_code_purpose"),
    ("VerificationCode", {"attempts_used": -1}, "attempts_negative"),
    ("VerificationCode", {"expires_at": STARTS_AT - timedelta(days=4000)}, "code_expired"),
    ("SignInLink", {"token_hash": "a" * 63}, "link_hash_63_characters"),
    ("SignInLink", {"expires_at": STARTS_AT - timedelta(days=4000)}, "link_expired"),
]

LEGAL_NEIGHBOURS = [
    ("Hospital", {"latitude": 90, "longitude": 180}, "latitude_90_longitude_180"),
    ("Hospital", {"latitude": -90, "longitude": -180}, "latitude_minus_90_longitude_minus_180"),
    ("Hospital", {"latitude": None, "longitude": None}, "no_coordinates"),
    ("Hospital", {"name": "H"}, "one_character_hospital_name"),
    ("Department", {"name": "D", "code": "d"}, "one_character_department_fields"),
    ("Specialty", {"name": "S", "code": "s"}, "one_character_specialty_fields"),
    ("User", {"email": "lower@example.com"}, "lower_case_email"),
    ("User", {**PATIENT_WITHOUT_PASSWORD, **VERIFIED}, "verified_passwordless_patient"),
    ("User", {"role": "CLINICIAN"}, "clinician_with_password"),
    ("ClinicianProfile", {"round_robin_weight": 1}, "round_robin_weight_one"),
    ("Room", {"capacity": 1}, "room_capacity_one"),
    ("AppointmentType", {"duration_minutes": 1}, "duration_one"),
    ("AppointmentType", {"buffer_minutes": 0}, "buffer_zero"),
    ("AppointmentType", {"colour": "#00ff7f"}, "colour_lower_case_hex"),
    ("AvailabilityRule", {"weekday": 0}, "weekday_zero"),
    ("AvailabilityRule", {"weekday": 6}, "weekday_six"),
    ("AvailabilityRule", {"slot_step_minutes": 5}, "slot_step_five"),
    ("AvailabilityRule", {"slot_step_minutes": 240}, "slot_step_240"),
    ("AvailabilityRule", {"start_time": time(9), "end_time": time(9, 1)}, "rule_one_minute_long"),
    ("AvailabilityRule", {"valid_to": date(2030, 1, 1)}, "valid_to_equals_valid_from"),
    ("TimeOff", {"ends_at": STARTS_AT + ONE_MINUTE}, "time_off_one_minute_long"),
    ("TimeOff", {"reason": "x" * 200}, "time_off_reason_200_characters"),
    ("Appointment", {"ends_at": STARTS_AT + ONE_MINUTE}, "appointment_one_minute_long"),
    ("Appointment", {"clinical_notes": "x" * 5000}, "notes_5000_characters"),
    (
        "Appointment",
        {"status": "CANCELLED", "cancelled_at": ENDS_AT, "cancellation_reason": "no longer needed"},
        "cancelled_with_time_and_reason",
    ),
    ("WaitlistEntry", {"latest_at": STARTS_AT + ONE_MINUTE}, "waitlist_window_one_minute"),
    ("Session", {"token_hash": SIXTY_FOUR}, "session_hash_64_characters"),
    ("BookingHold", {"ends_at": STARTS_AT + ONE_MINUTE}, "hold_one_minute_long"),
    ("BookingHold", {"visitor_email": "lower@example.com"}, "hold_lower_case_email"),
    ("VerificationCode", {"code_hash": SIXTY_FOUR}, "code_hash_64_characters"),
    ("VerificationCode", {"attempts_used": 0}, "attempts_zero"),
    ("SignInLink", {"token_hash": SIXTY_FOUR}, "link_hash_64_characters"),
    ("SignInLink", {"expires_at": FAR_FUTURE}, "link_expires_later"),
]


@pytest.mark.parametrize(
    ("model_name", "overrides"),
    [pytest.param(name, fields, id=label) for name, fields, label in ILLEGAL_ROWS],
)
def rejects_row_when_stored_value_breaks_a_rule_of_section_3(
    model_name: str, overrides: dict[str, object]
) -> None:
    refuses(model_name, **overrides)


@pytest.mark.parametrize(
    ("model_name", "overrides"),
    [pytest.param(name, fields, id=label) for name, fields, label in LEGAL_NEIGHBOURS],
)
def returns_stored_value_when_it_is_the_nearest_legal_one(
    model_name: str, overrides: dict[str, object]
) -> None:
    row = make(model_name, **overrides)

    stored = model_class(model_name)._default_manager.get(pk=row.pk)

    for field_name, expected in overrides.items():
        assert getattr(stored, field_name) == expected


@pytest.mark.parametrize("status", ["BOOKED", "CONFIRMED", "CHECKED_IN", "COMPLETED", "NO_SHOW"])
def returns_appointment_when_status_is_a_listed_value(status: str) -> None:
    row = make("Appointment", status=status)

    assert field_of(model_class("Appointment")._default_manager.get(pk=row.pk), "status") == status


@pytest.mark.parametrize("source", ["ONLINE", "ROUND_ROBIN", "STAFF"])
def returns_appointment_when_source_is_a_listed_value(source: str) -> None:
    row = make("Appointment", source=source)

    assert field_of(model_class("Appointment")._default_manager.get(pk=row.pk), "source") == source


@pytest.mark.parametrize("role", ["ADMIN", "CLINICIAN", "PATIENT"])
def returns_user_when_role_is_a_listed_value(role: str) -> None:
    row = make("User", role=role)

    assert field_of(model_class("User")._default_manager.get(pk=row.pk), "role") == role


@pytest.mark.parametrize(
    "kind",
    [
        "APPOINTMENT_REMINDER",
        "APPOINTMENT_CANCELLED",
        "SCHEDULE_CHANGED",
        "WAITLIST_OFFERED",
        "WAITLIST_BOOKED",
    ],
)
def returns_notification_when_kind_is_a_listed_value(kind: str) -> None:
    row = make("Notification", kind=kind)

    assert field_of(model_class("Notification")._default_manager.get(pk=row.pk), "kind") == kind


@pytest.mark.parametrize("status", ["WAITING", "BOOKED", "EXPIRED"])
def returns_waitlist_entry_when_status_is_a_listed_value_without_an_offer(status: str) -> None:
    row = make("WaitlistEntry", status=status)

    assert (
        field_of(model_class("WaitlistEntry")._default_manager.get(pk=row.pk), "status") == status
    )


def returns_waitlist_entry_when_offered_with_an_appointment() -> None:
    appointment = make("Appointment")

    row = make("WaitlistEntry", status="OFFERED", offered_appointment=appointment)

    stored = model_class("WaitlistEntry")._default_manager.get(pk=row.pk)
    assert field_of(stored, "status") == "OFFERED"
    assert field_of(stored, "offered_appointment_id") == appointment.pk


def rejects_waiting_entry_when_it_has_an_offered_appointment() -> None:
    appointment = make("Appointment")

    refuses("WaitlistEntry", status="WAITING", offered_appointment=appointment)


def rejects_second_offered_entry_when_same_appointment_is_offered() -> None:
    appointment = make("Appointment")
    make("WaitlistEntry", status="OFFERED", offered_appointment=appointment)

    refuses("WaitlistEntry", status="OFFERED", offered_appointment=appointment)


def returns_second_entry_when_first_offer_was_booked() -> None:
    appointment = make("Appointment")
    make("WaitlistEntry", status="BOOKED", offered_appointment=appointment)

    second = make("WaitlistEntry", status="OFFERED", offered_appointment=appointment)

    assert model_class("WaitlistEntry")._default_manager.filter(pk=second.pk).exists()
