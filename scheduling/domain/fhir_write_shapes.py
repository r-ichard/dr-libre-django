"""Task 23, spec 15.1: the shape of every body a write accepts, one entry per writable type."""

from scheduling.domain.fhir_appointment_write import APPOINTMENT_SHAPE
from scheduling.domain.fhir_body import Shape
from scheduling.domain.fhir_patient import PATIENT_SHAPE
from scheduling.domain.fhir_schedule import SCHEDULE_SHAPE

WRITE_SHAPES: dict[str, Shape] = {
    "Schedule": SCHEDULE_SHAPE,
    "Patient": PATIENT_SHAPE,
    "Appointment": APPOINTMENT_SHAPE,
}
