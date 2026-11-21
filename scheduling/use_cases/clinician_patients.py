"""Section 9.3: the patients of one clinician. The set is built from the clinician's own
appointments first; a search can only narrow it, so no other patient is ever reachable."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.patient_directory import last_and_next_visit, matches_name
from scheduling.domain.time_off_rules import FREED_STATUSES
from scheduling.models import Appointment, ClinicianProfile, User


@dataclass(frozen=True)
class PatientRow:
    name: str
    phone: str
    last_visit: datetime | None
    next_visit: datetime | None


def patients_of(profile: ClinicianProfile, query: str, now: datetime) -> list[PatientRow]:
    """A patient with only cancelled visits is listed, with no last or next visit."""
    patients: dict[UUID, User] = {}
    visit_starts: dict[UUID, list[datetime]] = {}
    for row in Appointment.objects.select_related("patient").filter(clinician=profile):
        patients[row.patient_id] = row.patient
        starts = visit_starts.setdefault(row.patient_id, [])
        if row.status not in FREED_STATUSES:
            starts.append(row.starts_at)
    found = []
    for key, patient in patients.items():
        if matches_name(patient.full_name, query):
            last_visit, next_visit = last_and_next_visit(now, visit_starts[key])
            found.append(PatientRow(patient.full_name, patient.phone, last_visit, next_visit))
    return sorted(found, key=lambda row: (row.name.casefold(), row.phone))
