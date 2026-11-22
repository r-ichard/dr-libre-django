"""Task 23, spec 15.1: the shape of every body a write accepts, one entry per writable type."""

from scheduling.domain.fhir_appointment_response import RESPONSE_SHAPE
from scheduling.domain.fhir_appointment_write import APPOINTMENT_SHAPE
from scheduling.domain.fhir_body import Shape
from scheduling.domain.fhir_communication import COMMUNICATION_SHAPE
from scheduling.domain.fhir_patient import PATIENT_SHAPE
from scheduling.domain.fhir_record_write import (
    LOCATION_SHAPE,
    ORGANIZATION_SHAPE,
    SERVICE_SHAPE,
)
from scheduling.domain.fhir_role_write import ROLE_SHAPE
from scheduling.domain.fhir_schedule import SCHEDULE_SHAPE
from scheduling.domain.fhir_specialty_write import CODE_SYSTEM_SHAPE

WRITE_SHAPES: dict[str, Shape] = {
    "Schedule": SCHEDULE_SHAPE,
    "PractitionerRole": ROLE_SHAPE,
    "Patient": PATIENT_SHAPE,
    "Appointment": APPOINTMENT_SHAPE,
    "AppointmentResponse": RESPONSE_SHAPE,
    "Communication": COMMUNICATION_SHAPE,
    "Organization": ORGANIZATION_SHAPE,
    "Location": LOCATION_SHAPE,
    "HealthcareService": SERVICE_SHAPE,
    "CodeSystem": CODE_SYSTEM_SHAPE,
}
