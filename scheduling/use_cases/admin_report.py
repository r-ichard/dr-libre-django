"""Section 13: what the admin dashboard shows for a range of days. Read only, six queries whatever
the number of appointments: zones, appointments, rules, time off, waitlist, busiest names."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from scheduling.domain.report_figures import (
    BusyClinician,
    DayCount,
    ReportedVisit,
    appointment_count,
    appointments_per_day,
    busiest_clinicians,
    cancellation_count,
    hospital_day,
    no_show_rate,
    online_share,
    waitlist_size,
)
from scheduling.domain.report_range import current_report_date, report_days
from scheduling.domain.report_utilisation import OffPeriod, RuleHours, utilisation
from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus, WaitlistStatus
from scheduling.models import (
    Appointment,
    AvailabilityRule,
    ClinicianProfile,
    Hospital,
    TimeOff,
    WaitlistEntry,
)
from scheduling.use_cases.request_context import current_request_context

APPOINTMENT_ZONE = "appointment_type__department__hospital__time_zone"
CLINICIAN_ZONE = "clinician__department__hospital__time_zone"


@dataclass(frozen=True)
class BusyRow:
    name: str
    count: int


@dataclass(frozen=True)
class Report:
    first_day: date
    last_day: date
    appointments: int
    cancellations: int
    utilisation: str
    no_show_rate: str
    online_share: str
    waitlist_size: int
    per_day: list[DayCount]
    busiest: list[BusyRow]


def build_report(raw_range: str) -> Report:
    zones = list(Hospital.objects.order_by().values_list("time_zone", flat=True).distinct())
    days = report_days(raw_range, current_report_date(current_request_context().now, zones))
    # Days are hospital-local, so fetch one UTC day more on each side and keep by local date.
    since = datetime.combine(days[0] - timedelta(days=1), time.min, UTC)
    before = datetime.combine(days[-1] + timedelta(days=2), time.min, UTC)
    visits = [visit for visit in _visits(since, before) if hospital_day(visit) in days]
    return Report(
        first_day=days[0],
        last_day=days[-1],
        appointments=appointment_count(visits),
        cancellations=cancellation_count(visits),
        utilisation=utilisation(visits, _rules(days), _time_off(since, before), days),
        no_show_rate=no_show_rate(visits),
        online_share=online_share(visits),
        waitlist_size=waitlist_size(_waitlist_statuses()),
        per_day=appointments_per_day(visits, days),
        busiest=_named(busiest_clinicians(visits)),
    )


def _visits(since: datetime, before: datetime) -> list[ReportedVisit]:
    rows = Appointment.objects.filter(starts_at__gte=since, starts_at__lt=before).values_list(
        "starts_at", "ends_at", "status", "source", APPOINTMENT_ZONE, "clinician_id"
    )
    return [
        ReportedVisit(
            starts_at, ends_at, AppointmentStatus(status), AppointmentSource(source), zone,
            str(clinician_id),
        )
        for starts_at, ends_at, status, source, zone, clinician_id in rows
    ]  # fmt: skip


def _rules(days: list[date]) -> list[RuleHours]:
    rows = AvailabilityRule.objects.filter(
        clinician__user__is_active=True, valid_from__lte=days[-1]
    ).exclude(valid_to__lt=days[0])
    return [
        RuleHours(str(clinician_id), weekday, start, end, valid_from, valid_to, zone)
        for clinician_id, weekday, start, end, valid_from, valid_to, zone in rows.values_list(
            "clinician_id", "weekday", "start_time", "end_time", "valid_from", "valid_to",
            CLINICIAN_ZONE,
        )
    ]  # fmt: skip


def _time_off(since: datetime, before: datetime) -> list[OffPeriod]:
    rows = TimeOff.objects.filter(
        clinician__user__is_active=True, starts_at__lt=before, ends_at__gt=since
    ).values_list("clinician_id", "starts_at", "ends_at")
    return [OffPeriod(str(clinician_id), start, end) for clinician_id, start, end in rows]


def _waitlist_statuses() -> list[WaitlistStatus]:
    rows = WaitlistEntry.objects.values_list("status", flat=True)
    return [WaitlistStatus(status) for status in rows]


def _named(busy: list[BusyClinician]) -> list[BusyRow]:
    names = dict(
        ClinicianProfile.objects.filter(pk__in=[row.clinician_id for row in busy]).values_list(
            "pk", "user__full_name"
        )
    )
    return [BusyRow(names[UUID(row.clinician_id)], row.count) for row in busy]
