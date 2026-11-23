"""/fhir access per interaction and caller, by drlibre-specs.md 15.4 and ADRs 0005 to 0010.
Read by the route-coverage test and the reads-and-searches walk. Data only.

No test_ prefix: pytest must not collect this data module."""

from dataclasses import dataclass
from enum import StrEnum


class Caller(StrEnum):
    VISITOR = "visitor"
    PATIENT = "patient"
    CLINICIAN = "clinician"
    ADMIN = "admin"


@dataclass(frozen=True)
class FhirAccessRow:
    resource: str
    interaction: str
    visitor: int
    patient: int
    clinician: int
    admin: int
    basis: str

    def answer_for(self, caller: Caller) -> int:
        answers = {
            Caller.VISITOR: self.visitor,
            Caller.PATIENT: self.patient,
            Caller.CLINICIAN: self.clinician,
            Caller.ADMIN: self.admin,
        }
        return answers[caller]


@dataclass(frozen=True)
class KnownDifference:
    """Both answers for one caller and interaction. The walk asserts the product's answer."""

    resource: str
    interaction: str
    caller: Caller
    row_answer: int
    product_answer: int


# Cells are HTTP statuses. Basis cites drlibre-specs.md 15.4 and the ADR that fills it in.
FHIR_ACCESS_ROWS: tuple[FhirAccessRow, ...] = (
    FhirAccessRow("Organization", "read", 200, 200, 200, 200, "15.4 anyone, active only"),
    FhirAccessRow("Organization", "search-type", 200, 200, 200, 200, "15.4 anyone, active only"),
    FhirAccessRow("Organization", "create", 401, 403, 403, 201, "15.4 admin; ADR 0008"),
    FhirAccessRow("Organization", "update", 401, 403, 403, 200, "15.4 admin; ADR 0008"),
    FhirAccessRow("Organization", "delete", 401, 403, 403, 200, "15.4 admin; ADR 0008"),
    FhirAccessRow("Location", "read", 200, 200, 200, 200, "15.4 anyone, active only"),
    FhirAccessRow("Location", "search-type", 200, 200, 200, 200, "15.4 anyone, active only"),
    FhirAccessRow("Location", "create", 401, 403, 403, 201, "15.4 admin"),
    FhirAccessRow("Location", "update", 401, 403, 403, 200, "15.4 admin"),
    FhirAccessRow("Location", "delete", 401, 403, 403, 200, "15.4 admin"),
    FhirAccessRow("HealthcareService", "read", 200, 200, 200, 200, "15.4 anyone, active only"),
    FhirAccessRow(
        "HealthcareService", "search-type", 200, 200, 200, 200, "15.4 anyone, active only"
    ),
    FhirAccessRow("HealthcareService", "create", 401, 403, 403, 201, "15.4 admin"),
    FhirAccessRow("HealthcareService", "update", 401, 403, 403, 200, "15.4 admin"),
    FhirAccessRow("HealthcareService", "delete", 401, 403, 403, 200, "15.4 admin"),
    FhirAccessRow("CodeSystem", "read", 200, 200, 200, 200, "15.4 anyone, active only"),
    FhirAccessRow("CodeSystem", "search-type", 200, 200, 200, 200, "15.4 anyone, active only"),
    FhirAccessRow("CodeSystem", "update", 401, 403, 403, 200, "15.4 admin; ADR 0008"),
    FhirAccessRow("ValueSet", "read", 200, 200, 200, 200, "15.4 anyone, active only"),
    FhirAccessRow("ValueSet", "search-type", 200, 200, 200, 200, "15.4 anyone, active only"),
    FhirAccessRow(
        "Practitioner", "read", 200, 200, 200, 200, "15.4 anyone, public fields; staff all"
    ),
    FhirAccessRow(
        "Practitioner", "search-type", 200, 200, 200, 200, "15.4 anyone, public fields; staff all"
    ),
    FhirAccessRow("Practitioner", "update", 401, 403, 403, 200, "15.4 admin"),
    FhirAccessRow("Practitioner", "delete", 401, 403, 403, 200, "15.4 admin"),
    FhirAccessRow(
        "PractitionerRole", "read", 200, 200, 200, 200, "15.4 anyone, public fields; staff all"
    ),
    FhirAccessRow(
        "PractitionerRole",
        "search-type",
        200,
        200,
        200,
        200,
        "15.4 anyone, public fields; staff all",
    ),
    FhirAccessRow("PractitionerRole", "create", 401, 403, 403, 201, "15.4 admin; ADR 0009"),
    FhirAccessRow(
        "PractitionerRole",
        "update",
        401,
        403,
        200,
        200,
        "15.4 clinician own notAvailable; ADR 0009",
    ),
    FhirAccessRow("PractitionerRole", "delete", 401, 403, 403, 200, "15.4 admin; ADR 0009"),
    FhirAccessRow("Schedule", "read", 200, 200, 200, 200, "15.4 anyone"),
    FhirAccessRow("Schedule", "search-type", 200, 200, 200, 200, "15.4 anyone"),
    FhirAccessRow("Schedule", "create", 401, 403, 201, 403, "15.4 owning clinician; ADR 0006"),
    FhirAccessRow("Schedule", "update", 401, 403, 200, 403, "15.4 owning clinician; ADR 0006"),
    FhirAccessRow("Schedule", "delete", 401, 403, 200, 403, "15.4 owning clinician; ADR 0006"),
    FhirAccessRow("Slot", "read", 200, 200, 200, 200, "15.4 anyone, free slots only"),
    FhirAccessRow("Slot", "search-type", 200, 200, 200, 200, "15.4 anyone, free slots only"),
    FhirAccessRow(
        "Patient", "read", 401, 200, 200, 200, "15.4 patient, clinician, admin; ADR 0006"
    ),
    FhirAccessRow(
        "Patient", "search-type", 401, 200, 200, 200, "15.4 patient, clinician, admin; ADR 0006"
    ),
    FhirAccessRow("Patient", "update", 401, 200, 403, 200, "15.4 patient, admin; ADR 0006"),
    FhirAccessRow("Appointment", "read", 401, 200, 200, 200, "15.4 patient, clinician, admin"),
    FhirAccessRow(
        "Appointment", "search-type", 401, 200, 200, 200, "15.4 patient, clinician, admin"
    ),
    FhirAccessRow("Appointment", "create", 401, 201, 201, 201, "15.4 and 5.4"),
    FhirAccessRow("Appointment", "update", 401, 200, 200, 200, "15.4 and 5.6; body-level (walk)"),
    FhirAccessRow("AppointmentResponse", "read", 401, 200, 403, 200, "15.4 patient own, admin"),
    FhirAccessRow(
        "AppointmentResponse",
        "search-type",
        401,
        200,
        403,
        200,
        "15.4 patient own, admin; ADR 0007",
    ),
    FhirAccessRow(
        "AppointmentResponse",
        "create",
        401,
        201,
        403,
        201,
        "15.4 patient own offer, admin; ADR 0007",
    ),
    FhirAccessRow("Communication", "read", 401, 200, 403, 403, "15.4 recipient; ADR 0005 owner"),
    FhirAccessRow(
        "Communication", "search-type", 401, 200, 403, 403, "15.4 recipient; ADR 0005 owner"
    ),
    FhirAccessRow("Communication", "update", 401, 200, 403, 403, "15.4 recipient; ADR 0005 owner"),
    FhirAccessRow("AuditEvent", "read", 401, 403, 403, 200, "15.4 admin; ADR 0007"),
    FhirAccessRow("AuditEvent", "search-type", 401, 403, 403, 200, "15.4 admin; ADR 0007"),
)

# Pairs the product answers otherwise than its row. Each is a finding for the review's "For the
# owner" section; the walk holds the product's answer until the owner decides.
KNOWN_DIFFERENCES: tuple[KnownDifference, ...] = (
    KnownDifference("Slot", "search-type", Caller.VISITOR, 200, 400),
    KnownDifference("Slot", "search-type", Caller.PATIENT, 200, 400),
    KnownDifference("Slot", "search-type", Caller.CLINICIAN, 200, 400),
    KnownDifference("Slot", "search-type", Caller.ADMIN, 200, 400),
    KnownDifference("Communication", "search-type", Caller.CLINICIAN, 403, 200),
    KnownDifference("Communication", "search-type", Caller.ADMIN, 403, 200),
    KnownDifference("AppointmentResponse", "search-type", Caller.CLINICIAN, 403, 200),
)
