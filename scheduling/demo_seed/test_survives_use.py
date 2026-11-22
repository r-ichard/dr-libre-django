"""Task 17e: the seed survives a person using the demo world between two runs."""

from contextlib import AbstractContextManager
from datetime import UTC, date, datetime, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.utils import timezone

from scheduling.demo_seed import booking, scenarios
from scheduling.demo_seed.booking import expect
from scheduling.demo_seed.scenarios import AppointmentSeed
from scheduling.demo_seed.seed_support import FIXED_NOW, seed_environment
from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import AppointmentSource as Source
from scheduling.domain.vocabulary import AppointmentStatus as Status
from scheduling.domain.vocabulary import WaitlistStatus
from scheduling.models import (
    Appointment,
    AuditLogEntry,
    ClinicianProfile,
    Notification,
    TimeOff,
    User,
    WaitlistEntry,
)
from scheduling.models.booking import ClinicalNote, NotificationKind
from scheduling.use_cases.appointment_changes import (
    cancel_appointment,
    change_status,
    reschedule_appointment,
)
from scheduling.use_cases.clinical_notes import save_clinical_note
from scheduling.use_cases.notification_inbox import mark_read
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.time_off import TimeOffCommand, create_time_off
from scheduling.use_cases.waitlist import accept_offer

pytestmark = pytest.mark.django_db

__all__ = ["seed_environment"]

TWO_DAYS = timedelta(days=2)
SATURDAY = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
SUNDAY = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
FINISHED = {Status.COMPLETED, Status.NO_SHOW, Status.CHECKED_IN}
PATIENT_EMAIL = "patient@example.test"
HEART_EMAIL = "clinician@example.test"


def _seed_at(moment: datetime) -> str:
    output = StringIO()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(timezone, "now", lambda: moment)
        call_command("seed_demo", stdout=output)
    return output.getvalue()


def _as_person(moment: datetime) -> AbstractContextManager[None]:
    return bind_request_context(RequestContext("person-acts", moment))


def _user(email: str) -> User:
    return User.objects.get(email=email)


def _booked_of(patient_email: str) -> Appointment:
    booked = Appointment.objects.filter(patient__email=patient_email, status=Status.BOOKED)
    found = booked.order_by("-starts_at").first()
    assert found is not None
    return found


def returns_no_error_and_keeps_both_rows_when_patient_accepted_the_seeded_offer(
    seed_environment: None,
) -> None:
    _seed_at(FIXED_NOW)
    entry = WaitlistEntry.objects.get(patient__email=PATIENT_EMAIL, status=WaitlistStatus.OFFERED)
    with _as_person(FIXED_NOW):
        expect(accept_offer(entry.pk, entry.patient))
    accepted = Appointment.objects.get(waitlist_entry=entry)

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert Appointment.objects.filter(pk=accepted.pk, version=accepted.version).exists()
    assert WaitlistEntry.objects.filter(pk=entry.pk).exists()


def returns_keeps_appointment_when_clinician_rescheduled_it(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)
    target = _booked_of(PATIENT_EMAIL)
    moved_to = target.starts_at + timedelta(days=7)
    with _as_person(FIXED_NOW):
        expect(reschedule_appointment(target.pk, moved_to, target.clinician.user))

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert Appointment.objects.filter(pk=target.pk, starts_at=moved_to).exists()


def returns_keeps_appointment_when_cancelled_by_patient(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)
    target = _booked_of("passwordless@example.test")
    with _as_person(FIXED_NOW):
        expect(cancel_appointment(target.pk, "Cannot come", target.patient))

    _seed_at(FIXED_NOW + TWO_DAYS)

    kept = Appointment.objects.get(pk=target.pk)
    assert (kept.status, kept.cancellation_reason) == (Status.CANCELLED, "Cannot come")


def returns_keeps_appointment_when_clinician_changed_status(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)
    target = _booked_of(PATIENT_EMAIL)
    with _as_person(FIXED_NOW):
        expect(change_status(target.pk, Status.CHECKED_IN, target.clinician.user))

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert Appointment.objects.get(pk=target.pk).status == Status.CHECKED_IN


def returns_keeps_appointment_and_note_when_clinician_wrote_clinical_note(
    seed_environment: None,
) -> None:
    _seed_at(FIXED_NOW)
    target = _booked_of(PATIENT_EMAIL)
    with _as_person(FIXED_NOW):
        expect(save_clinical_note(target.pk, "Follow up in a week", target.clinician.user))

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert ClinicalNote.objects.filter(appointment_id=target.pk).exists()


def returns_keeps_notification_and_parent_when_patient_read_it(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)
    target = _booked_of(PATIENT_EMAIL)
    notice = Notification.objects.filter(appointment=target, read_at__isnull=True).first()
    assert notice is not None
    with _as_person(FIXED_NOW):
        expect(mark_read(notice.pk, target.patient))

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert Notification.objects.filter(pk=notice.pk, read_at__isnull=False).exists()
    assert Appointment.objects.filter(pk=target.pk).exists()


def returns_replaces_untouched_rows_when_world_rebuilds(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)
    target = _booked_of(PATIENT_EMAIL)

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert not Appointment.objects.filter(pk=target.pk).exists()


def returns_leaves_person_time_off_unchanged_when_world_rebuilds(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)
    clinician = ClinicianProfile.objects.get(user__email=scenarios.CHILD)
    start = FIXED_NOW + timedelta(days=90)
    with _as_person(FIXED_NOW):
        command = TimeOffCommand(start, start + timedelta(days=2), "Annual leave")
        expect(create_time_off(command, clinician.user))
    own = TimeOff.objects.get(clinician=clinician, starts_at=start)

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert TimeOff.objects.filter(pk=own.pk, version=own.version).exists()


def returns_keeps_pending_notification_pending_when_it_is_committed_during_the_run(
    seed_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_at(FIXED_NOW)
    real_build = booking.WorldBuilder.build

    def build_and_receive_real_notification(builder: booking.WorldBuilder) -> None:
        real_build(builder)
        Notification.objects.create(
            recipient=_user(PATIENT_EMAIL),
            kind=NotificationKind.APPOINTMENT_CANCELLED,
            title="Appointment cancelled",
            email_pending=True,
        )

    monkeypatch.setattr(booking.WorldBuilder, "build", build_and_receive_real_notification)

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert Notification.objects.filter(email_pending=True, appointment__isnull=True).count() == 1


@pytest.mark.parametrize("clock", [FIXED_NOW, SATURDAY, SUNDAY])
def returns_no_skipped_scenario_when_database_is_empty(
    seed_environment: None, clock: datetime
) -> None:
    output = _seed_at(clock)

    assert "skipped:" not in output
    for seed in scenarios.APPOINTMENTS:
        assert Appointment.objects.filter(
            patient__email=seed.patient_email,
            clinician__user__email=seed.clinician_email,
            appointment_type__code=seed.type_code,
        ).exists()
    for wish in scenarios.WAITLIST_ENTRIES:
        assert WaitlistEntry.objects.filter(
            patient__email=wish.patient_email, appointment_type__code=wish.type_code
        ).exists()


@pytest.mark.parametrize("clock", [SATURDAY, SUNDAY])
def returns_places_finished_visits_before_and_upcoming_after_now_when_clock_is_a_weekend(
    seed_environment: None, clock: datetime
) -> None:
    _seed_at(clock)

    for appointment in Appointment.objects.filter(status__in=FINISHED):
        assert appointment.starts_at <= clock
    for appointment in Appointment.objects.filter(status=Status.BOOKED):
        assert appointment.starts_at > clock


def returns_rebuilds_once_when_run_in_three_zones_on_one_utc_day(seed_environment: None) -> None:
    _seed_at(datetime(2026, 11, 17, 12, 0, tzinfo=UTC))
    first_day = datetime(2026, 11, 18, 0, 30, tzinfo=UTC)
    _seed_at(first_day)
    audit_after_first = AuditLogEntry.objects.count()

    _seed_at(datetime(2026, 11, 18, 9, 0, tzinfo=UTC))
    _seed_at(datetime(2026, 11, 18, 23, 30, tzinfo=UTC))

    assert AuditLogEntry.objects.count() == audit_after_first


def returns_prints_built_and_kept_lines_when_a_person_used_a_row(seed_environment: None) -> None:
    first = _seed_at(FIXED_NOW)
    target = _booked_of(PATIENT_EMAIL)
    with _as_person(FIXED_NOW):
        expect(change_status(target.pk, Status.CHECKED_IN, target.clinician.user))

    second = _seed_at(FIXED_NOW + TWO_DAYS)

    assert "built Appointment:" in first
    assert "kept Appointment: 1 (used by a person)" in second


def returns_an_unread_notification_when_a_demo_patient_has_an_upcoming_appointment(
    seed_environment: None,
) -> None:
    _seed_at(FIXED_NOW)

    upcoming = Appointment.objects.filter(status=Status.BOOKED, starts_at__gt=FIXED_NOW)
    for patient_id in set(upcoming.values_list("patient_id", flat=True)):
        assert Notification.objects.filter(recipient_id=patient_id, read_at__isnull=True).exists()


def _waiting_seeded_entry() -> WaitlistEntry:
    found = WaitlistEntry.objects.filter(status=WaitlistStatus.WAITING).order_by("pk").first()
    assert found is not None
    return found


def returns_keeps_entry_when_a_person_changed_it(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)
    entry = _waiting_seeded_entry()
    entry.latest_at += timedelta(days=1)
    entry.save()

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert WaitlistEntry.objects.filter(pk=entry.pk, latest_at=entry.latest_at).exists()


def returns_keeps_entry_when_an_unseeded_appointment_points_to_it(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)
    entry = _waiting_seeded_entry()
    template = Appointment.objects.filter(patient=entry.patient).first()
    assert template is not None
    own = Appointment.objects.create(
        patient=entry.patient,
        clinician=template.clinician,
        appointment_type=entry.appointment_type,
        starts_at=FIXED_NOW + timedelta(days=60),
        ends_at=FIXED_NOW + timedelta(days=60, minutes=30),
        status=Status.BOOKED,
        source="STAFF",
        waitlist_entry=entry,
    )

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert Appointment.objects.filter(pk=own.pk).exists()
    assert WaitlistEntry.objects.filter(pk=entry.pk).exists()


def returns_keeps_appointment_when_an_unseeded_entry_was_offered_it(
    seed_environment: None,
) -> None:
    _seed_at(FIXED_NOW)
    freed = Appointment.objects.filter(status=Status.CANCELLED).order_by("pk").first()
    assert freed is not None
    own = WaitlistEntry.objects.create(
        patient=_user("patient.six@example.test"),
        appointment_type=freed.appointment_type,
        earliest_at=FIXED_NOW,
        latest_at=FIXED_NOW + timedelta(days=30),
        status=WaitlistStatus.OFFERED,
        offered_appointment=freed,
    )

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert Appointment.objects.filter(pk=freed.pk).exists()
    assert WaitlistEntry.objects.filter(pk=own.pk).exists()


def returns_keeps_time_off_when_a_person_changed_it(seed_environment: None) -> None:
    _seed_at(FIXED_NOW)
    seeded = TimeOff.objects.order_by("pk").first()
    assert seeded is not None
    seeded.reason = "Changed by the clinician"
    seeded.save()

    _seed_at(FIXED_NOW + TWO_DAYS)

    assert TimeOff.objects.filter(pk=seeded.pk, reason="Changed by the clinician").exists()


def returns_the_day_before_the_weekend_when_a_past_cancelled_visit_is_placed(
    seed_environment: None,
) -> None:
    zone = ZoneInfo("America/New_York")
    cancelled_past = AppointmentSeed(
        scenarios.NEW_YORK_OTHER, scenarios.GENERAL, scenarios.VIDEO, -6, 12, Status.CANCELLED,
        Source.STAFF,
    )  # fmt: skip

    placed = scenarios.starts_at_for(SATURDAY, zone, cancelled_past)

    assert placed.astimezone(zone).date() == date(2026, 11, 12)
