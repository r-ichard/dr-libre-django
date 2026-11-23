"""The records the /fhir reads and searches are walked on: two clinicians, an admin and two
patients, each patient with a direct booking, a waitlist booking, a notification and an audit."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.test import Client

from scheduling.domain.fhir_slot_id import slot_id
from scheduling.models import (
    Appointment,
    AppointmentType,
    AuditLogEntry,
    AvailabilityRule,
    ClinicianProfile,
    Notification,
    Room,
    User,
    WaitlistEntry,
)
from scheduling.models.builders import STARTS_AT, add_clinician, make, make_clinic, make_user
from scheduling.views.fhir_test_support import client_for, token_of
from test_support.fhir_access_rows import Caller

APPOINTMENT_LENGTH = timedelta(minutes=30)
FREE_START = STARTS_AT + timedelta(hours=1)
WAITLIST_START = STARTS_AT + timedelta(hours=3)


@dataclass(frozen=True)
class World:
    room: Room
    appointment_type: AppointmentType
    rule: AvailabilityRule
    clinician: ClinicianProfile
    other_clinician: ClinicianProfile
    patient: User
    other_patient: User
    admin: User
    appointment: Appointment
    other_appointment: Appointment
    waitlist_entry: WaitlistEntry
    other_waitlist_entry: WaitlistEntry
    notification: Notification
    other_notification: Notification
    audit_entry: AuditLogEntry
    other_audit_entry: AuditLogEntry
    free_slot_id: str
    clients: dict[Caller, Client]


def _booking(
    patient: User, clinician: ClinicianProfile, appointment_type: AppointmentType, start: datetime
) -> Appointment:
    appointment = make(
        "Appointment",
        patient=patient,
        clinician=clinician,
        appointment_type=appointment_type,
        starts_at=start,
        ends_at=start + APPOINTMENT_LENGTH,
    )
    assert isinstance(appointment, Appointment)
    return appointment


def _waitlist_booking(
    patient: User, clinician: ClinicianProfile, appointment_type: AppointmentType
) -> WaitlistEntry:
    entry = make(
        "WaitlistEntry", patient=patient, appointment_type=appointment_type, status="BOOKED"
    )
    assert isinstance(entry, WaitlistEntry)
    make(
        "Appointment",
        patient=patient,
        clinician=clinician,
        appointment_type=appointment_type,
        starts_at=WAITLIST_START,
        ends_at=WAITLIST_START + APPOINTMENT_LENGTH,
        waitlist_entry=entry,
    )
    return entry


def _notification(recipient: User) -> Notification:
    notification = make("Notification", recipient=recipient)
    assert isinstance(notification, Notification)
    return notification


def _audit_entry() -> AuditLogEntry:
    entry = make("AuditLogEntry")
    assert isinstance(entry, AuditLogEntry)
    return entry


def _clients(patient: User, clinician: ClinicianProfile, admin: User) -> dict[Caller, Client]:
    return {
        Caller.VISITOR: client_for(None),
        Caller.PATIENT: client_for(token_of(patient)),
        Caller.CLINICIAN: client_for(token_of(clinician.user)),
        Caller.ADMIN: client_for(token_of(admin)),
    }


def _build_world() -> World:
    clinic = make_clinic()
    clinician = clinic.clinician
    other_clinician = add_clinician(clinic.department)
    room = make("Room", department=clinic.department)
    assert isinstance(room, Room)
    rule = AvailabilityRule.objects.get(clinician=clinician)
    appointment_type = clinic.appointment_type
    patient = clinic.patient
    other_patient = make_user(role="PATIENT")
    admin = make_user(role="ADMIN")
    return World(
        room=room,
        appointment_type=appointment_type,
        rule=rule,
        clinician=clinician,
        other_clinician=other_clinician,
        patient=patient,
        other_patient=other_patient,
        admin=admin,
        appointment=_booking(patient, clinician, appointment_type, STARTS_AT),
        other_appointment=_booking(other_patient, other_clinician, appointment_type, STARTS_AT),
        waitlist_entry=_waitlist_booking(patient, clinician, appointment_type),
        other_waitlist_entry=_waitlist_booking(other_patient, other_clinician, appointment_type),
        notification=_notification(patient),
        other_notification=_notification(other_patient),
        audit_entry=_audit_entry(),
        other_audit_entry=_audit_entry(),
        free_slot_id=slot_id(rule.pk, appointment_type.pk, FREE_START),
        clients=_clients(patient, clinician, admin),
    )
