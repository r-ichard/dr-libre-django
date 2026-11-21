"""Section 9.3 reads: the signed-in clinician's own rules, time off and rooms, and the
appointments a period of time off would cover. Always filtered by the clinician's profile."""

from datetime import datetime

from scheduling.domain.time_off_rules import PlannedVisit, appointments_inside
from scheduling.models import Appointment, AvailabilityRule, ClinicianProfile, Room, TimeOff


def own_rules(profile: ClinicianProfile) -> list[AvailabilityRule]:
    return list(
        AvailabilityRule.objects.select_related("room")
        .filter(clinician=profile)
        .order_by("weekday", "start_time", "pk")
    )


def own_time_off(profile: ClinicianProfile) -> list[TimeOff]:
    return list(TimeOff.objects.filter(clinician=profile).order_by("starts_at", "pk"))


def bookable_rooms(profile: ClinicianProfile) -> list[Room]:
    return list(
        Room.objects.filter(department=profile.department, is_active=True).order_by("name", "pk")
    )


def appointments_in(
    profile: ClinicianProfile, starts_at: datetime, ends_at: datetime
) -> list[Appointment]:
    """The clinician's active appointments that overlap the period; none are changed."""
    rows = list(
        Appointment.objects.select_related("patient", "appointment_type")
        .filter(clinician=profile, starts_at__lt=ends_at, ends_at__gt=starts_at)
        .order_by("starts_at", "pk")
    )
    visits = [PlannedVisit(str(row.pk), row.starts_at, row.ends_at, row.status) for row in rows]
    kept = {visit.label for visit in appointments_inside(starts_at, ends_at, visits)}
    return [row for row in rows if str(row.pk) in kept]
