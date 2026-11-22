"""Section 10: what the admin record pages read: a page of one record's list, one record, the
counts of what depends on it, the parents to choose from."""

from datetime import datetime
from functools import reduce
from operator import or_
from uuid import UUID

from django.db.models import Model, Q

from scheduling.domain.appointment_status import ACTIVE_STATUSES
from scheduling.domain.clinician_rules import WeeklyHours, availability_summary
from scheduling.domain.search_ordering import Page, page_bounds
from scheduling.domain.vocabulary import Role
from scheduling.models import (
    Appointment,
    AppointmentType,
    AuditLogEntry,
    AvailabilityRule,
    ClinicianProfile,
    Department,
    Hospital,
    Room,
    Specialty,
    User,
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
    "user": {
        "appointments_as_patient": (Appointment, "patient_id"),
        "appointments_as_clinician": (Appointment, "clinician__user_id"),
        "audit_entries": (AuditLogEntry, "actor_id"),
        "clinician_profile": (ClinicianProfile, "user_id"),
        "waitlist_entries": (WaitlistEntry, "patient_id"),
    },
    "clinician": {"appointments": (Appointment, "clinician_id")},
}


def dependent_counts(kind: str, record_id: UUID) -> dict[str, int]:
    return {
        reason: model._default_manager.filter(**{column: record_id}).count()
        for reason, (model, column) in DEPENDENTS[kind].items()
    }


def list_records(kind: str, query: str, page: int) -> Page[Model]:
    spec = SPECS[kind]
    rows = spec.all_rows().order_by(*spec.order_by)
    if query:
        rows = rows.filter(
            reduce(or_, (Q(**{f"{name}__icontains": query}) for name in spec.search_fields))
        )
    if spec.select_related:
        rows = rows.select_related(*spec.select_related)
    total = rows.count()
    bounds = page_bounds(total, page, PAGE_SIZE)
    shown = list(rows[bounds.first : bounds.first + PAGE_SIZE])
    return Page(shown, total, bounds.page, bounds.page_count)


def find_record(kind: str, record_id: UUID) -> Versioned | None:
    spec = SPECS[kind]
    rows = spec.all_rows()
    if spec.select_related:
        rows = rows.select_related(*spec.select_related)
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


def upcoming_for_clinician(profile_id: UUID, now: datetime) -> int:
    return Appointment.objects.filter(
        clinician_id=profile_id,
        starts_at__gt=now,
        status__in=[status.value for status in ACTIVE_STATUSES],
    ).count()


def upcoming_for_user(user_id: UUID, now: datetime) -> int:
    """Upcoming booked appointments of a patient or of a clinician; they stay booked."""
    return Appointment.objects.filter(
        Q(patient_id=user_id) | Q(clinician__user_id=user_id),
        starts_at__gt=now,
        status__in=[status.value for status in ACTIVE_STATUSES],
    ).count()


def list_extras(kind: str, rows: list[Model]) -> dict[UUID, str]:
    """The one column a list computes: weekly availability of each clinician on the page."""
    if kind != "clinician":
        return {}
    by_profile: dict[UUID, list[WeeklyHours]] = {row.pk: [] for row in rows}
    for rule in AvailabilityRule.objects.filter(clinician_id__in=by_profile):
        by_profile[rule.clinician_id].append(
            WeeklyHours(rule.weekday, rule.start_time, rule.end_time)
        )
    return {key: availability_summary(hours) for key, hours in by_profile.items()}


def role_choices() -> list[tuple[str, str]]:
    return [(role.value, role.value.capitalize()) for role in Role]


def clinician_user_choices() -> list[tuple[str, str]]:
    """Active clinician users who have no profile yet."""
    users = User.objects.filter(role=Role.CLINICIAN, is_active=True, clinicianprofile__isnull=True)
    return [(str(row.pk), row.full_name) for row in users.order_by("full_name", "id")]


def specialty_choices() -> list[tuple[str, str]]:
    rows = Specialty.objects.filter(is_active=True).order_by("name", "id")
    return [(str(row.pk), row.name) for row in rows]


def room_choices() -> list[tuple[str, str]]:
    rooms = Room.objects.filter(is_active=True).select_related("department__hospital")
    return [
        (str(row.pk), f"{row.name}, {row.department.name}, {row.department.hospital.name}")
        for row in rooms.order_by("name", "id")
    ]
