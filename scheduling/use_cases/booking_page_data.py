"""Read-only loaders of the booking pages: what a page may show, and nothing it may not."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.booking_codes import MAXIMUM_ATTEMPTS, code_is_usable
from scheduling.domain.booking_week import group_by_local_day, week_range
from scheduling.domain.email_mask import mask_email
from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.models import (
    Appointment,
    AppointmentType,
    BookingHold,
    ClinicianProfile,
    User,
    VerificationCode,
)
from scheduling.models.access import HoldSource
from scheduling.use_cases.free_slots_query import find_free_slots
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.schedule_loading import active_appointment_type, department_clinicians

PAST_WEEKS_SHOWN = 52
FUTURE_WEEKS_SHOWN = 104


@dataclass(frozen=True)
class SlotChoice:
    appointment_type: AppointmentType
    clinician: ClinicianProfile | None


@dataclass(frozen=True)
class WeekOfSlots:
    choice: SlotChoice
    time_zone: ZoneInfo
    week_start: date
    days: dict[date, list[datetime]]


@dataclass(frozen=True)
class HoldSummary:
    appointment_type_id: UUID
    pinned_clinician_id: UUID | None
    masked_email: str
    attempts_left: int


def slot_choice(appointment_type_id: UUID, clinician_id: UUID | None) -> SlotChoice | None:
    appointment_type = active_appointment_type(appointment_type_id)
    if appointment_type is None:
        return None
    if clinician_id is None:
        return SlotChoice(appointment_type, None)
    clinician = (
        department_clinicians(appointment_type, clinician_id)
        .select_related("user", "specialty")
        .first()
    )
    return None if clinician is None else SlotChoice(appointment_type, clinician)


def week_of_slots(
    appointment_type_id: UUID, clinician_id: UUID | None, asked_week: date | None
) -> Result[WeekOfSlots]:
    choice = slot_choice(appointment_type_id, clinician_id)
    if choice is None:
        return Failure.not_found()
    time_zone = ZoneInfo(choice.appointment_type.department.hospital.time_zone)
    week_start = _week_shown(asked_week, time_zone)
    window = week_range(week_start, time_zone)
    found = find_free_slots(appointment_type_id, clinician_id, window)
    if isinstance(found, Failure):
        return found
    starts = [offer.start for offer in found.value.offers]
    days = group_by_local_day(starts, time_zone)
    return Success(WeekOfSlots(choice, time_zone, week_start, days))


def hold_summary(hold_id: UUID) -> HoldSummary | None:
    now = current_request_context().now
    hold = BookingHold.objects.filter(pk=hold_id, expires_at__gt=now).first()
    if hold is None:
        return None
    stored = VerificationCode.objects.filter(hold=hold).first()
    usable = stored is not None and code_is_usable(stored.expires_at, stored.attempts_used, now)
    attempts_left = MAXIMUM_ATTEMPTS - stored.attempts_used if stored and usable else 0
    pinned = hold.clinician_id if hold.source == HoldSource.ONLINE else None
    return HoldSummary(
        hold.appointment_type_id, pinned, mask_email(hold.visitor_email), attempts_left
    )


def appointment_for_patient(appointment_id: UUID, patient: User) -> Appointment | None:
    return (
        Appointment.objects.select_related(
            "clinician__user",
            "clinician__specialty",
            "appointment_type__department__hospital",
            "room",
        )
        .filter(pk=appointment_id, patient=patient)
        .exclude(status=AppointmentStatus.CANCELLED)
        .first()
    )


def _week_shown(asked_week: date | None, time_zone: ZoneInfo) -> date:
    """A week far outside the booking horizon is the current one, so date arithmetic cannot
    overflow on an address someone typed."""
    today = current_request_context().now.astimezone(time_zone).date()
    earliest = today - timedelta(weeks=PAST_WEEKS_SHOWN)
    latest = today + timedelta(weeks=FUTURE_WEEKS_SHOWN)
    if asked_week is None or not earliest <= asked_week <= latest:
        return today - timedelta(days=today.weekday())
    return asked_week - timedelta(days=asked_week.weekday())
