"""Section 10: what the admin appointment pages read: the filtered list, one appointment with
what an admin may see of it, and the choices of the filter form. Writes stay in the use cases
of tasks 07 and 08."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import reduce
from operator import or_
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import Q, QuerySet

from scheduling.domain.search_ordering import Page, page_bounds
from scheduling.models import Appointment, ClinicianProfile, Department, Hospital

PAGE_SIZE = 20
NEWEST_FIRST = ("-starts_at", "-pk")
HOSPITAL_ZONE = "appointment_type__department__hospital__time_zone"


@dataclass(frozen=True)
class AdminAppointmentFilters:
    first_day: date | None = None
    last_day: date | None = None
    department_id: UUID | None = None
    clinician_id: UUID | None = None
    status: str = ""
    source: str = ""


def matching_appointments(filters: AdminAppointmentFilters) -> QuerySet[Appointment]:
    matching = Appointment.objects.all()
    if filters.department_id is not None:
        matching = matching.filter(appointment_type__department_id=filters.department_id)
    if filters.clinician_id is not None:
        matching = matching.filter(clinician_id=filters.clinician_id)
    if filters.status:
        matching = matching.filter(status=filters.status)
    if filters.source:
        matching = matching.filter(source=filters.source)
    if filters.first_day is not None or filters.last_day is not None:
        matching = matching.filter(_days_in_each_hospital_zone(filters))
    return matching


def list_appointments_for_admin(filters: AdminAppointmentFilters, page: int) -> Page[Appointment]:
    matching = matching_appointments(filters)
    total = matching.count()
    bounds = page_bounds(total, page, PAGE_SIZE)
    rows = matching.select_related(
        "patient", "clinician__user", "appointment_type__department__hospital"
    ).order_by(*NEWEST_FIRST)[bounds.first : bounds.first + PAGE_SIZE]
    return Page(list(rows), total, bounds.page, bounds.page_count)


def _days_in_each_hospital_zone(filters: AdminAppointmentFilters) -> Q:
    """A calendar day is a day of the hospital's wall clock, so each zone gets its own bounds."""
    zones = Hospital.objects.order_by().values_list("time_zone", flat=True).distinct()
    return reduce(or_, (_days_in_zone(filters, ZoneInfo(zone)) for zone in zones), Q(pk__in=[]))


def _days_in_zone(filters: AdminAppointmentFilters, zone: ZoneInfo) -> Q:
    condition = Q(**{HOSPITAL_ZONE: str(zone)})
    if filters.first_day is not None:
        start = datetime.combine(filters.first_day, time.min, zone).astimezone(UTC)
        condition &= Q(starts_at__gte=start)
    if filters.last_day is not None:
        after = datetime.combine(filters.last_day + timedelta(days=1), time.min, zone)
        condition &= Q(starts_at__lt=after.astimezone(UTC))
    return condition


def appointment_for_admin(appointment_id: UUID) -> Appointment | None:
    return (
        Appointment.objects.select_related(
            "patient", "clinician__user", "room", "appointment_type__department__hospital"
        )
        .filter(pk=appointment_id)
        .first()
    )


def filter_departments() -> list[Department]:
    return list(Department.objects.select_related("hospital").order_by("hospital__name", "name"))


def filter_clinicians() -> list[ClinicianProfile]:
    return list(ClinicianProfile.objects.select_related("user").order_by("user__full_name", "pk"))
