"""Section 9.1 and 9.2: read loaders of the clinician workspace. Every query is filtered by the
signed-in clinician's own profile, never by an id from the request."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import QuerySet

from scheduling.domain.appointment_status import ACTIVE_STATUSES
from scheduling.domain.booking_week import week_range
from scheduling.domain.failure import Failure
from scheduling.domain.free_slots import TimeRange
from scheduling.domain.workspace_day import local_day_bounds
from scheduling.models import Appointment, AppointmentType, ClinicianProfile, TimeOff, User
from scheduling.use_cases.free_slots_query import find_free_slots

NEXT_FREE_SLOT_DAYS = 14


def clinician_profile_of(user: User) -> ClinicianProfile | None:
    return ClinicianProfile.objects.select_related("department__hospital").filter(user=user).first()


def day_agenda(profile: ClinicianProfile, day: date) -> list[Appointment]:
    start, end = local_day_bounds(day, profile.department.hospital.time_zone)
    return list(
        _with_details()
        .filter(clinician=profile, starts_at__gte=start, starts_at__lt=end)
        .order_by("starts_at", "pk")
    )


def week_appointments(profile: ClinicianProfile, week_start: date) -> list[Appointment]:
    window = _week_window(profile, week_start)
    return list(
        _with_details()
        .filter(
            clinician=profile,
            status__in=ACTIVE_STATUSES,
            starts_at__lt=window.ends_at,
            ends_at__gt=window.starts_at,
        )
        .order_by("starts_at", "pk")
    )


def week_time_off(profile: ClinicianProfile, week_start: date) -> list[TimeOff]:
    window = _week_window(profile, week_start)
    return list(
        TimeOff.objects.filter(
            clinician=profile, starts_at__lt=window.ends_at, ends_at__gt=window.starts_at
        ).order_by("starts_at", "pk")
    )


def department_types(profile: ClinicianProfile) -> list[AppointmentType]:
    """Retired types too: an old appointment keeps its colour."""
    return list(AppointmentType.objects.filter(department=profile.department).order_by("pk"))


def next_free_slot(profile: ClinicianProfile, now: datetime) -> datetime | None:
    """The first slot of the shortest active type of the department, or None within 14 days."""
    shortest = (
        AppointmentType.objects.filter(department=profile.department, is_active=True)
        .order_by("duration_minutes", "pk")
        .first()
    )
    if shortest is None:
        return None
    window = TimeRange(now, now + timedelta(days=NEXT_FREE_SLOT_DAYS))
    found = find_free_slots(shortest.pk, profile.pk, window)
    if isinstance(found, Failure) or not found.value.offers:
        return None
    return min(offer.start for offer in found.value.offers)


def _week_window(profile: ClinicianProfile, week_start: date) -> TimeRange:
    return week_range(week_start, ZoneInfo(profile.department.hospital.time_zone))


def _with_details() -> QuerySet[Appointment]:
    return Appointment.objects.select_related(
        "patient", "appointment_type", "room", "clinician__user"
    )
