"""Task 03: what the seeded world contains, and that running it again changes nothing."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from scheduling.demo_seed.seed_support import FIXED_NOW, row_counts, run_seed, seed_environment
from scheduling.models import (
    Appointment,
    AppointmentType,
    Hospital,
    Notification,
    Room,
    User,
    WaitlistEntry,
)

pytestmark = pytest.mark.django_db

__all__ = ["seed_environment"]

DAYS_LATER = [1, 2, 3, 9, 40]
ALL_APPOINTMENT_STATUSES = {
    "BOOKED", "CHECKED_IN", "COMPLETED", "CANCELLED", "NO_SHOW",
}  # fmt: skip
ALL_APPOINTMENT_SOURCES = {"ONLINE", "ROUND_ROBIN", "STAFF"}
ALL_WAITLIST_STATUSES = {"WAITING", "OFFERED", "BOOKED", "EXPIRED"}


def _seed_at(days_after_fixed_clock: int) -> None:
    clock = FIXED_NOW + timedelta(days=days_after_fixed_clock)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(timezone, "now", lambda: clock)
        run_seed()


def returns_same_row_counts_when_command_runs_twice_on_one_day(seed_environment: None) -> None:
    _seed_at(0)
    first = row_counts()

    _seed_at(0)

    second = row_counts()
    assert second == first


def returns_same_row_counts_when_command_runs_on_a_later_day(seed_environment: None) -> None:
    _seed_at(0)
    first = row_counts()
    first_starts = sorted(Appointment.objects.values_list("starts_at", flat=True))

    for days in DAYS_LATER:
        _seed_at(days)
        counts = row_counts()
        counts.pop("AuditLogEntry")
        assert counts == {name: first[name] for name in counts}

    shifted = sorted(Appointment.objects.values_list("starts_at", flat=True))
    assert shifted[0] - first_starts[0] >= timedelta(days=DAYS_LATER[-1] - 1)


def returns_past_today_and_upcoming_appointments_when_seeded(seed_environment: None) -> None:
    _seed_at(0)

    appointments = list(Appointment.objects.select_related("clinician__department__hospital"))

    assert any(each.ends_at < FIXED_NOW for each in appointments)
    assert any(each.starts_at > FIXED_NOW for each in appointments)
    assert any(
        each.starts_at.astimezone(ZoneInfo(each.clinician.department.hospital.time_zone)).date()
        == FIXED_NOW.astimezone(ZoneInfo(each.clinician.department.hospital.time_zone)).date()
        for each in appointments
    )


def returns_finished_appointments_before_today_and_open_ones_from_today_when_seeded(
    seed_environment: None,
) -> None:
    _seed_at(0)

    def local_date(appointment: Appointment) -> tuple[date, date]:
        zone = ZoneInfo(appointment.clinician.department.hospital.time_zone)
        return appointment.starts_at.astimezone(zone).date(), FIXED_NOW.astimezone(zone).date()

    appointments = Appointment.objects.select_related("clinician__department__hospital")
    for each in appointments.filter(status__in=["COMPLETED", "NO_SHOW"]):
        day, today = local_date(each)
        assert day <= today
    for each in appointments.filter(status="BOOKED"):
        day, today = local_date(each)
        assert day >= today
    assert len({local_date(each)[0] for each in appointments}) >= 6


def returns_every_appointment_status_and_source_when_seeded(seed_environment: None) -> None:
    _seed_at(0)

    assert set(Appointment.objects.values_list("status", flat=True)) == ALL_APPOINTMENT_STATUSES
    assert set(Appointment.objects.values_list("source", flat=True)) == ALL_APPOINTMENT_SOURCES


def returns_every_waitlist_status_when_seeded(seed_environment: None) -> None:
    _seed_at(0)

    assert set(WaitlistEntry.objects.values_list("status", flat=True)) == ALL_WAITLIST_STATUSES


def returns_read_and_unread_notifications_when_seeded(seed_environment: None) -> None:
    _seed_at(0)

    assert Notification.objects.filter(read_at__isnull=False).count() >= 2
    assert Notification.objects.filter(read_at__isnull=True).count() >= 2


def returns_two_time_zones_and_one_hospital_without_coordinates_when_seeded(
    seed_environment: None,
) -> None:
    _seed_at(0)

    assert Hospital.objects.values("time_zone").distinct().count() >= 2
    assert Hospital.objects.filter(latitude__isnull=True, longitude__isnull=True).exists()
    assert Hospital.objects.filter(latitude__isnull=False, longitude__isnull=False).exists()


def returns_room_need_and_online_variety_when_appointment_types_are_seeded(
    seed_environment: None,
) -> None:
    _seed_at(0)

    for flag in ("needs_room", "is_bookable_online"):
        assert AppointmentType.objects.filter(**{flag: True}).exists()
        assert AppointmentType.objects.filter(**{flag: False}).exists()


def returns_end_equal_to_start_plus_duration_when_seeded(seed_environment: None) -> None:
    _seed_at(0)

    for appointment in Appointment.objects.select_related("appointment_type"):
        duration = timedelta(minutes=appointment.appointment_type.duration_minutes)
        assert appointment.ends_at == appointment.starts_at + duration


def returns_same_department_for_clinician_type_and_rooms_when_seeded(
    seed_environment: None,
) -> None:
    _seed_at(0)

    for appointment in Appointment.objects.select_related("clinician", "appointment_type", "room"):
        department_id = appointment.clinician.department_id
        assert appointment.appointment_type.department_id == department_id
        if appointment.room is not None:
            assert appointment.room.department_id == department_id
            assert appointment.appointment_type.needs_room is True
        else:
            assert appointment.appointment_type.needs_room is False
    assert Room.objects.filter(is_active=True).exists()


def returns_roles_clinician_and_patient_when_checking_appointment_people(
    seed_environment: None,
) -> None:
    _seed_at(0)

    for appointment in Appointment.objects.select_related("patient", "clinician__user"):
        assert appointment.patient.role == "PATIENT"
        assert appointment.clinician.user.role == "CLINICIAN"


def returns_booked_appointment_linked_to_entry_when_waitlist_entry_is_booked(
    seed_environment: None,
) -> None:
    _seed_at(0)

    booked_entries = WaitlistEntry.objects.filter(status="BOOKED")

    assert booked_entries.exists()
    for entry in booked_entries:
        assert Appointment.objects.filter(waitlist_entry=entry).exists()


def returns_cancelled_appointment_when_waitlist_entry_is_offered(seed_environment: None) -> None:
    _seed_at(0)

    for entry in WaitlistEntry.objects.filter(status="OFFERED").select_related(
        "offered_appointment"
    ):
        assert entry.offered_appointment is not None
        assert entry.offered_appointment.status == "CANCELLED"


def returns_only_example_test_addresses_and_reserved_phones_when_seeded(
    seed_environment: None,
) -> None:
    _seed_at(0)

    for person in User.objects.all():
        assert person.email.endswith("@example.test")
        assert person.phone == "" or person.phone.startswith("+44 20 7946 0")
    for hospital in Hospital.objects.all():
        assert hospital.phone.startswith("+44 20 7946 0")


def returns_reminder_only_once_per_appointment_when_seeded(seed_environment: None) -> None:
    _seed_at(0)
    _seed_at(0)

    reminders = Notification.objects.filter(kind="APPOINTMENT_REMINDER", appointment__isnull=False)

    assert reminders.values("appointment").distinct().count() == reminders.count()
