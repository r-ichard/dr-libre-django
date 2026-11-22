"""Section 10: what the admin record pages read: a page of one record's list, one record, the
counts of what depends on it, the parents to choose from."""

from datetime import datetime
from uuid import UUID

from django.db.models import Model, Q

from scheduling.domain.appointment_status import ACTIVE_STATUSES
from scheduling.domain.search_ordering import Page, paginate
from scheduling.models import (
    Appointment,
    AppointmentType,
    AvailabilityRule,
    ClinicianProfile,
    Department,
    Hospital,
    Room,
    WaitlistEntry,
)
from scheduling.models.base import Versioned
from scheduling.use_cases.admin_record_specs import SPECS

PAGE_SIZE = 20
# Per kind and reason: the model that points at the record, and through which column.
DEPENDENTS: dict[str, dict[str, tuple[type[Model], str]]] = {
    "hospital": {"departments": (Department, "hospital_id")},
    "department": {
        "clinicians": (ClinicianProfile, "department_id"),
        "rooms": (Room, "department_id"),
        "appointment_types": (AppointmentType, "department_id"),
    },
    "specialty": {"clinicians": (ClinicianProfile, "specialty_id")},
    "room": {
        "appointments": (Appointment, "room_id"),
        "availability_rules": (AvailabilityRule, "room_id"),
        "default_room_clinicians": (ClinicianProfile, "default_room_id"),
    },
    "appointment_type": {
        "appointments": (Appointment, "appointment_type_id"),
        "waitlist_entries": (WaitlistEntry, "appointment_type_id"),
    },
}


def dependent_counts(kind: str, record_id: UUID) -> dict[str, int]:
    return {
        reason: model._default_manager.filter(**{column: record_id}).count()
        for reason, (model, column) in DEPENDENTS[kind].items()
    }


def list_records(kind: str, query: str, page: int) -> Page[Model]:
    rows = SPECS[kind].all_rows().order_by("name", "id")
    if query:
        rows = rows.filter(Q(name__icontains=query) | Q(code__icontains=query))
    parent = SPECS[kind].parent_form_name
    if parent:
        rows = rows.select_related(parent)
    return paginate(list(rows), max(1, page), PAGE_SIZE)


def find_record(kind: str, record_id: UUID) -> Versioned | None:
    spec = SPECS[kind]
    rows = spec.all_rows()
    if spec.parent_form_name:
        rows = rows.select_related(spec.parent_form_name)
    record = rows.filter(pk=record_id).first()
    return record if isinstance(record, Versioned) else None


def parent_choices(kind: str) -> list[tuple[str, str]]:
    """Value and text of every possible parent; a department is told apart by its hospital."""
    parent_model = SPECS[kind].parent_model
    if parent_model is Department:
        departments = Department.objects.select_related("hospital").order_by("name", "id")
        return [(str(row.pk), f"{row.name}, {row.hospital.name}") for row in departments]
    if parent_model is Hospital:
        return [(str(row.pk), row.name) for row in Hospital.objects.order_by("name", "id")]
    return []


def upcoming_appointment_count(hospital_id: UUID, now: datetime) -> int:
    return Appointment.objects.filter(
        clinician__department__hospital_id=hospital_id,
        starts_at__gt=now,
        status__in=[status.value for status in ACTIVE_STATUSES],
    ).count()
