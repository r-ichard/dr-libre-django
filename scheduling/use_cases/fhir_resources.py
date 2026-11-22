"""Task 23, spec 15.1: the one place `/fhir` turns a type name into a use case. A type with its
own rules (Slot, Patient, and the writes) is routed here; the rest read through `fhir_reads`."""

from uuid import UUID

from scheduling.domain.failure import Failure, Result
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_search import SearchQuery
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_patient_reads import read_patient, search_patients
from scheduling.use_cases.fhir_patient_writes import update_patient
from scheduling.use_cases.fhir_reads import SearchPage, read_resource, search_resource
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
    return read_resource(resource_type, identifier, caller.viewer)


def search(resource_type: str, query: SearchQuery, caller: Caller) -> Result[SearchPage]:
    if resource_type == "Slot":
        return search_slots(query, caller)
    if resource_type == "Patient":
        return search_patients(query, caller)
    return search_resource(resource_type, query, caller.viewer)


def create(resource_type: str, body: dict[str, object], caller: Caller) -> Result[Resource]:
    if resource_type == "Schedule":
        return create_schedule(body, caller)
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
    return Failure.not_found()


def delete(
    resource_type: str, identifier: UUID, caller: Caller, expected_version: int | None
) -> Result[None]:
    if resource_type == "Schedule":
        return delete_schedule(identifier, caller, expected_version)
    return Failure.not_found()
