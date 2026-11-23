"""Read-only loaders of the booking pages: what a page may show, and nothing it may not."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.booking_codes import MAXIMUM_ATTEMPTS, code_is_usable
from scheduling.domain.booking_rules import LEAD_TIME
from scheduling.domain.booking_week import group_by_local_day, week_range
from scheduling.domain.email_mask import mask_email
from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.free_slots import TimeRange
from scheduling.domain.search_matching import HORIZON
from scheduling.domain.slot_search import MAXIMUM_QUERY_DAYS
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


def slot_choice(
    appointment_type_id: UUID, clinician_id: UUID | None, online_only: bool
) -> SlotChoice | None:
    appointment_type = active_appointment_type(appointment_type_id, online_only)
    if appointment_type is None:
        return None
    if clinician_id is None:
        return SlotChoice(appointment_type, None)
    clinician = (
        department_clinicians(appointment_type, clinician_id, online_only)
        .select_related("user", "specialty")
        .first()
    )
    return None if clinician is None else SlotChoice(appointment_type, clinician)


def week_of_slots(
    appointment_type_id: UUID,
    clinician_id: UUID | None,
    asked_week: date | None,
    online_only: bool,
    *,
    open_on_first_free: bool = False,
) -> Result[WeekOfSlots]:
    choice = slot_choice(appointment_type_id, clinician_id, online_only)
    if choice is None:
        return Failure.not_found()
    time_zone = ZoneInfo(choice.appointment_type.department.hospital.time_zone)
    week_start = _week_shown(asked_week, time_zone)
    found = find_free_slots(
        appointment_type_id, clinician_id, week_range(week_start, time_zone), online_only
    )
    if isinstance(found, Failure):
        return found
    if open_on_first_free and asked_week is None and not found.value.offers:
        first_free = _first_free_start(appointment_type_id, clinician_id, online_only)
        if isinstance(first_free, Failure):
            return first_free
        if first_free.value is not None:
            week_start = _week_shown(first_free.value.astimezone(time_zone).date(), time_zone)
            found = find_free_slots(
                appointment_type_id, clinician_id, week_range(week_start, time_zone), online_only
            )
            if isinstance(found, Failure):
                return found
    starts = [offer.start for offer in found.value.offers]
    days = group_by_local_day(starts, time_zone)
    return Success(WeekOfSlots(choice, time_zone, week_start, days))


def slot_is_offered(choice: SlotChoice, starts_at: datetime, online_only: bool) -> bool:
    """True when `starts_at` is one of the free times the booking pages list for this choice."""
    appointment_type = choice.appointment_type
    window = TimeRange(starts_at, starts_at + timedelta(minutes=appointment_type.duration_minutes))
    clinician_id = choice.clinician.pk if choice.clinician else None
    found = find_free_slots(appointment_type.pk, clinician_id, window, online_only)
    return not isinstance(found, Failure) and any(
        offer.start == starts_at for offer in found.value.offers
    )


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


def _first_free_start(
    appointment_type_id: UUID, clinician_id: UUID | None, online_only: bool
) -> Result[datetime | None]:
    """The earliest free start in the booking horizon, searched in chunks of at most 31 days."""
    now = current_request_context().now
    horizon_end = now + HORIZON
    chunk_start = now + LEAD_TIME
    while True:
        chunk_end = min(chunk_start + timedelta(days=MAXIMUM_QUERY_DAYS), horizon_end)
        found = find_free_slots(
            appointment_type_id, clinician_id, TimeRange(chunk_start, chunk_end), online_only
        )
        if isinstance(found, Failure):
            return found
        if found.value.offers:
            return Success(found.value.offers[0].start)
        if chunk_end >= horizon_end:
            return Success(None)
        # A slot that starts in the last duration of this chunk can end in the next one.
        chunk_start = chunk_end - found.value.duration


@dataclass(frozen=True)
class DepartmentServices:
    name: str
    types: list[AppointmentType]


@dataclass(frozen=True)
class HospitalServices:
    name: str
    departments: list[DepartmentServices]


def bookable_services(online_only: bool = True) -> list[HospitalServices]:
    """Active types, grouped hospital then department, in name order. Staff pass online_only
    False and see the types that are not bookable online too."""
    types = AppointmentType.objects.filter(
        is_active=True, department__hospital__is_active=True
    ).select_related("department__hospital")
    if online_only:
        types = types.filter(is_bookable_online=True)
    ordered = types.order_by("department__hospital__name", "department__name", "name")
    hospitals: dict[str, dict[str, list[AppointmentType]]] = {}
    for appointment_type in ordered:
        department = appointment_type.department
        by_department = hospitals.setdefault(department.hospital.name, {})
        by_department.setdefault(department.name, []).append(appointment_type)
    return [
        HospitalServices(
            hospital, [DepartmentServices(name, found) for name, found in departments.items()]
        )
        for hospital, departments in hospitals.items()
    ]


def type_providers(
    appointment_type_id: UUID, online_only: bool
) -> tuple[AppointmentType, list[ClinicianProfile]] | None:
    appointment_type = active_appointment_type(appointment_type_id, online_only)
    if appointment_type is None:
        return None
    clinicians = department_clinicians(appointment_type, None, online_only).select_related(
        "user", "specialty"
    )
    return appointment_type, list(clinicians.order_by("user__full_name"))
