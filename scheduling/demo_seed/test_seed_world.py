"""Section 16: the seeded world obeys the rules the product enforces."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core import mail
from django.utils import timezone

from scheduling.demo_seed.seed_support import FIXED_NOW, row_counts, run_seed, seed_environment
from scheduling.models import (
    Appointment,
    AuditLogEntry,
    AvailabilityRule,
    ClinicianProfile,
    Notification,
    TimeOff,
)

pytestmark = pytest.mark.django_db

__all__ = ["seed_environment"]

MONDAY_TO_FRIDAY = {1, 2, 3, 4, 5}
CALENDAR_OPENS = time(7, 0)
CALENDAR_CLOSES = time(19, 0)
SECTION_ELEVEN_TITLES = {
    "Appointment booked", "Appointment rescheduled", "Appointment cancelled",
    "Waitlist slot offered", "Waitlist slot booked", "Appointment reminder",
}  # fmt: skip


def _seed_at(moment: datetime) -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(timezone, "now", lambda: moment)
        run_seed()


def _spec_weekday(local_moment: datetime) -> int:
    return (local_moment.weekday() + 1) % 7


def _zone(clinician: ClinicianProfile) -> ZoneInfo:
    return ZoneInfo(clinician.department.hospital.time_zone)


def returns_weekdays_one_to_five_when_seeded(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)

    for clinician in ClinicianProfile.objects.all():
        weekdays = set(
            AvailabilityRule.objects.filter(clinician=clinician).values_list("weekday", flat=True)
        )
        assert weekdays == MONDAY_TO_FRIDAY


def returns_every_appointment_inside_a_rule_and_outside_time_off_when_seeded(
    seed_environment: None,
) -> None:
    _seed_at(FIXED_NOW)

    appointments = Appointment.objects.select_related("clinician__department__hospital")
    assert appointments.exists()
    for appointment in appointments:
        zone = _zone(appointment.clinician)
        start = appointment.starts_at.astimezone(zone)
        end = appointment.ends_at.astimezone(zone)
        rules = AvailabilityRule.objects.filter(
            clinician=appointment.clinician, weekday=_spec_weekday(start)
        )
        assert any(
            rule.start_time <= start.time() and end.time() <= rule.end_time for rule in rules
        )
        assert start.time() >= CALENDAR_OPENS and end.time() <= CALENDAR_CLOSES
        assert start.date() == end.date()
        assert not TimeOff.objects.filter(
            clinician=appointment.clinician,
            starts_at__lt=appointment.ends_at,
            ends_at__gt=appointment.starts_at,
        ).exists()
        appointment.full_clean()
        appointment.validate_constraints()


def returns_whole_local_days_when_time_off_is_seeded(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)

    periods = TimeOff.objects.select_related("clinician__department__hospital")
    assert periods.exists()
    for period in periods:
        zone = _zone(period.clinician)
        assert period.starts_at.astimezone(zone).time() == time(0, 0)
        assert period.ends_at.astimezone(zone).time() == time(0, 0)


def returns_section_11_titles_when_notifications_are_seeded(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)

    titles = set(Notification.objects.values_list("title", flat=True))
    assert titles
    assert titles <= SECTION_ELEVEN_TITLES


def returns_an_audit_entry_per_seeded_booking_when_seeded(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)

    for appointment in Appointment.objects.all():
        assert AuditLogEntry.objects.filter(
            entity_type="Appointment", entity_id=str(appointment.pk), action="appointment.book"
        ).exists()


def returns_no_mail_and_no_pending_rows_when_seeded(
    seed_environment: None, django_capture_on_commit_callbacks: object
) -> None:
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        _seed_at(FIXED_NOW)

    assert mail.outbox == []
    assert not Notification.objects.filter(email_pending=True).exists()


def returns_no_change_and_no_audit_entry_when_run_twice_on_one_day(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)
    first = row_counts()
    first_versions = sorted(Appointment.objects.values_list("pk", "version"))

    _seed_at(FIXED_NOW)

    assert row_counts() == first
    assert sorted(Appointment.objects.values_list("pk", "version")) == first_versions


@pytest.mark.parametrize("days_later", [1, 2, 3])
def returns_open_appointments_on_weekdays_when_run_on_any_later_day(
    seed_environment: None, days_later: int
) -> None:
    _seed_at(FIXED_NOW)

    _seed_at(FIXED_NOW + timedelta(days=days_later))

    for appointment in Appointment.objects.select_related("clinician__department__hospital"):
        local = appointment.starts_at.astimezone(_zone(appointment.clinician))
        assert _spec_weekday(local) in MONDAY_TO_FRIDAY


def returns_clinician_with_today_appointments_in_every_reachable_status(
    seed_environment: None,
) -> None:
    _seed_at(FIXED_NOW)

    zone = ZoneInfo("Europe/Berlin")
    today = FIXED_NOW.astimezone(zone).date()
    statuses = {
        each.status
        for each in Appointment.objects.filter(clinician__user__email="clinician@example.test")
        if each.starts_at.astimezone(zone).date() == today
    }
    assert statuses == {"COMPLETED", "NO_SHOW", "CHECKED_IN", "BOOKED", "CANCELLED"}
