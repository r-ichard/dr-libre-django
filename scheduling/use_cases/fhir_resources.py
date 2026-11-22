"""Task 23, spec 15.1: the one place `/fhir` turns a type name into a use case. A type with its
own rules (Slot, Patient, and the writes) is routed here; the rest read through `fhir_reads`."""

from uuid import UUID

from scheduling.domain.failure import Failure, Result
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_search import SearchQuery
from scheduling.use_cases.fhir_appointment_reads import read_appointment, search_appointments
from scheduling.use_cases.fhir_appointment_writes import create_appointment, update_appointment
from scheduling.use_cases.fhir_audit_reads import read_audit_event, search_audit_events
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_communication_reads import (
    read_communication,
    search_communications,
    update_communication,
)
from scheduling.use_cases.fhir_patient_reads import read_patient, search_patients
from scheduling.use_cases.fhir_patient_writes import update_patient
from scheduling.use_cases.fhir_reads import SearchPage, read_resource, search_resource
from scheduling.use_cases.fhir_record_writes import (
    RECORD_TYPES,
    create_record_resource,
    delete_record_resource,
    is_hospital_organization,
    update_record_resource,
    write_refusal,
)
from scheduling.use_cases.fhir_response_reads import (
    create_response,
    read_response,
    search_responses,
)
from scheduling.use_cases.fhir_schedule_writes import (
    create_schedule,
    delete_schedule,
    update_schedule,
)
from scheduling.use_cases.fhir_slot_reads import read_slot, search_slots


def read(resource_type: str, identifier: str, caller: Caller) -> Result[Resource]:
    if resource_type == "Slot":
        return read_slot(identifier, caller)
    if resource_type == "Patient":
        return read_patient(identifier, caller)
    if resource_type == "Appointment":
        return read_appointment(identifier, caller)
    if resource_type == "AppointmentResponse":
        return read_response(identifier, caller)
    if resource_type == "Communication":
        return read_communication(identifier, caller)
    if resource_type == "AuditEvent":
        return read_audit_event(identifier, caller)
    return read_resource(resource_type, identifier, caller.viewer)


def search(resource_type: str, query: SearchQuery, caller: Caller) -> Result[SearchPage]:
    if resource_type == "Slot":
        return search_slots(query, caller)
    if resource_type == "Patient":
        return search_patients(query, caller)
    if resource_type == "Appointment":
        return search_appointments(query, caller)
    if resource_type == "AppointmentResponse":
        return search_responses(query, caller)
    if resource_type == "Communication":
        return search_communications(query, caller)
    if resource_type == "AuditEvent":
        return search_audit_events(query, caller)
    return search_resource(resource_type, query, caller.viewer)


def create(resource_type: str, body: dict[str, object], caller: Caller) -> Result[Resource]:
    if resource_type == "Schedule":
        return create_schedule(body, caller)
    if resource_type == "Appointment":
        return create_appointment(body, caller)
    if resource_type == "AppointmentResponse":
        return create_response(body, caller)
    if resource_type in RECORD_TYPES:
        return create_record_resource(resource_type, body, caller)
    return Failure.not_found()


def update(
    resource_type: str,
    identifier: UUID,
    body: dict[str, object],
    caller: Caller,
    expected_version: int | None,
) -> Result[Resource]:
    if resource_type == "Schedule":
        return update_schedule(identifier, body, caller, expected_version)
    if resource_type == "Patient":
        return update_patient(identifier, body, caller, expected_version)
    if resource_type == "Appointment":
        return update_appointment(identifier, body, caller, expected_version)
    if resource_type == "Communication":
        return update_communication(identifier, body, caller, expected_version)
    if resource_type in RECORD_TYPES:
        return update_record_resource(resource_type, identifier, body, caller, expected_version)
    return Failure.not_found()


def delete(
    resource_type: str, identifier: UUID, caller: Caller, expected_version: int | None
) -> Result[None]:
    if resource_type == "Schedule":
        return delete_schedule(identifier, caller, expected_version)
    if resource_type in RECORD_TYPES:
        return delete_record_resource(resource_type, identifier, caller, expected_version)
    return Failure.not_found()


def is_read_only_here(resource_type: str, identifier: UUID) -> bool:
    """The record exists but this type is only its read-only view (a hospital's Organization)."""
    return is_hospital_organization(resource_type, identifier)


def refusal_before_body(resource_type: str, caller: Caller) -> Failure | None:
    return write_refusal(resource_type, caller)
