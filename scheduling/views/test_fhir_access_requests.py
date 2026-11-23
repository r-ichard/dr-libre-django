"""The request each /fhir read and parameterless search receives from each caller, sent as a FHIR
client sends it: a bearer token or none, no cookie, no Origin (client_for)."""

from collections.abc import Callable

from django.http import HttpResponseBase

from scheduling.views.test_fhir_access_world import World
from test_support.fhir_access_rows import Caller, FhirAccessRow

READ_INTERACTION = "read"
SEARCH_INTERACTION = "search-type"

# The record each read names, out of the records of test_fhir_access_world.
READ_PATHS: dict[str, Callable[[World], str]] = {
    "Organization": lambda world: f"/fhir/Organization/{world.room.department.hospital_id}",
    "Location": lambda world: f"/fhir/Location/{world.room.pk}",
    "HealthcareService": lambda world: f"/fhir/HealthcareService/{world.appointment_type.pk}",
    "CodeSystem": lambda _world: "/fhir/CodeSystem/specialty",
    "ValueSet": lambda _world: "/fhir/ValueSet/specialty",
    "Practitioner": lambda world: f"/fhir/Practitioner/{world.clinician.user_id}",
    "PractitionerRole": lambda world: f"/fhir/PractitionerRole/{world.clinician.pk}",
    "Schedule": lambda world: f"/fhir/Schedule/{world.rule.pk}",
    "Slot": lambda world: f"/fhir/Slot/{world.free_slot_id}",
    "Patient": lambda world: f"/fhir/Patient/{world.patient.pk}",
    "Appointment": lambda world: f"/fhir/Appointment/{world.appointment.pk}",
    "AppointmentResponse": lambda world: f"/fhir/AppointmentResponse/{world.waitlist_entry.pk}",
    "Communication": lambda world: f"/fhir/Communication/{world.notification.pk}",
    "AuditEvent": lambda world: f"/fhir/AuditEvent/{world.audit_entry.pk}",
}

# The record of another user each personal read names.
OTHER_USER_PATHS: dict[str, Callable[[World], str]] = {
    "Patient": lambda world: f"/fhir/Patient/{world.other_patient.pk}",
    "Appointment": lambda world: f"/fhir/Appointment/{world.other_appointment.pk}",
    "AppointmentResponse": lambda world: (
        f"/fhir/AppointmentResponse/{world.other_waitlist_entry.pk}"
    ),
    "Communication": lambda world: f"/fhir/Communication/{world.other_notification.pk}",
    "AuditEvent": lambda world: f"/fhir/AuditEvent/{world.other_audit_entry.pk}",
}


def _path_of(row: FhirAccessRow, world: World) -> str:
    if row.interaction == READ_INTERACTION:
        return READ_PATHS[row.resource](world)
    return f"/fhir/{row.resource}"


def _send(world: World, caller: Caller, path: str) -> HttpResponseBase:
    return world.clients[caller].get(path)
