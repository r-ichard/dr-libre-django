"""Section 14 GET /appointments: what the caller may see, filtered, in pages."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db.models import QuerySet

from scheduling.domain.vocabulary import AppointmentStatus, Role
from scheduling.models import Appointment, User


@dataclass(frozen=True)
class AppointmentFilters:
    patient_id: UUID | None
    clinician_id: UUID | None
    status: AppointmentStatus | None
    starts_from: datetime | None
    starts_before: datetime | None


@dataclass(frozen=True)
class AppointmentPage:
    count: int
    rows: list[Appointment]


def list_appointments(
    actor: User, filters: AppointmentFilters, page: int, page_size: int
) -> AppointmentPage:
    matching = _narrowed(_visible_to(actor), filters).order_by("starts_at", "pk")
    offset = (page - 1) * page_size
    rows = matching.select_related("appointment_type__department__hospital")
    return AppointmentPage(matching.count(), list(rows[offset : offset + page_size]))


def _visible_to(actor: User) -> QuerySet[Appointment]:
    """The scope comes first and from the session; a filter can only narrow it further."""
    appointments = Appointment.objects.all()
    match Role(actor.role):
        case Role.ADMIN:
            return appointments
        case Role.CLINICIAN:
            return appointments.filter(clinician__user=actor)
        case Role.PATIENT:
            return appointments.filter(patient=actor)


def _narrowed(
    appointments: QuerySet[Appointment], filters: AppointmentFilters
) -> QuerySet[Appointment]:
    if filters.patient_id is not None:
        appointments = appointments.filter(patient_id=filters.patient_id)
    if filters.clinician_id is not None:
        appointments = appointments.filter(clinician_id=filters.clinician_id)
    if filters.status is not None:
        appointments = appointments.filter(status=filters.status)
    if filters.starts_from is not None:
        appointments = appointments.filter(starts_at__gte=filters.starts_from)
    if filters.starts_before is not None:
        appointments = appointments.filter(starts_at__lt=filters.starts_before)
    return appointments
