from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db.models import (
    PROTECT,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    Func,
    Index,
    OneToOneField,
    PositiveIntegerField,
    Q,
    TextChoices,
    TextField,
    UniqueConstraint,
)
from django.utils import timezone

from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus, WaitlistStatus
from scheduling.models.base import (
    Record,
    Versioned,
    check,
    choices_of,
    ends_after_start,
    not_blank,
    one_of,
)
from scheduling.models.organisation import AppointmentType, Room
from scheduling.models.people import ClinicianProfile, User

CLINICAL_NOTES_MAXIMUM = 5000
TITLE_MAXIMUM = 200


class NotificationKind(TextChoices):
    APPOINTMENT_REMINDER = "APPOINTMENT_REMINDER"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    SCHEDULE_CHANGED = "SCHEDULE_CHANGED"
    WAITLIST_OFFERED = "WAITLIST_OFFERED"
    WAITLIST_BOOKED = "WAITLIST_BOOKED"


class TimestampRange(Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


def _no_overlap(resource: str) -> ExclusionConstraint:
    """Half-open range, so appointments that touch are legal; the two statuses that free the
    slot are left out of the constraint."""
    return ExclusionConstraint(
        name=f"appointment_no_overlap_for_{resource}",
        expressions=[
            (TimestampRange("starts_at", "ends_at", RangeBoundary()), RangeOperators.OVERLAPS),
            (resource, RangeOperators.EQUAL),
        ],
        condition=~Q(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
        violation_error_message=f"the {resource} already has an appointment at that time",
    )


class Appointment(Versioned):
    fhir_resources = ("Appointment",)
    patient = ForeignKey(User, on_delete=PROTECT)
    clinician = ForeignKey(ClinicianProfile, on_delete=PROTECT)
    appointment_type = ForeignKey(AppointmentType, on_delete=PROTECT)
    room = ForeignKey(Room, null=True, blank=True, on_delete=PROTECT)
    starts_at = DateTimeField()
    ends_at = DateTimeField()
    status = CharField(max_length=20, choices=choices_of(AppointmentStatus))
    source = CharField(max_length=20, choices=choices_of(AppointmentSource))
    patient_reason = TextField(blank=True, default="")
    cancelled_at = DateTimeField(null=True, blank=True)
    cancellation_reason = TextField(blank=True, default="")
    # Section 15.3: an accepted entry and its booking are one FHIR resource, so the booking
    # continues the entry's version: versionId = inherited_version + version (ADR 0003).
    waitlist_entry = OneToOneField("WaitlistEntry", null=True, blank=True, on_delete=PROTECT)
    inherited_version = PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            check(
                "appointment_inherited_version_only_from_waitlist",
                Q(waitlist_entry__isnull=False) | Q(inherited_version=0),
                "an inherited version needs a waitlist entry",
            ),
            ends_after_start("appointment", "starts_at", "ends_at"),
            one_of("appointment", "status", AppointmentStatus),
            one_of("appointment", "source", AppointmentSource),
            check(
                "appointment_cancellation_only_when_cancelled",
                (
                    Q(status=AppointmentStatus.CANCELLED, cancelled_at__isnull=False)
                    & ~Q(cancellation_reason="")
                )
                | (
                    ~Q(status=AppointmentStatus.CANCELLED)
                    & Q(cancelled_at__isnull=True, cancellation_reason="")
                ),
                "cancellation time and reason exist exactly when the status is CANCELLED",
            ),
            _no_overlap("clinician"),
            _no_overlap("patient"),
            _no_overlap("room"),
        ]


class ClinicalNote(Record):
    """Private to the appointment's clinician, so it lives apart from the Appointment row that
    the API, emails and admin loaders read."""

    fhir_not_exposed = "private to the clinician; never in an API body, notification or email"
    appointment = OneToOneField(Appointment, on_delete=PROTECT)
    clinical_notes = CharField(max_length=CLINICAL_NOTES_MAXIMUM, blank=True, default="")


class WaitlistEntry(Versioned):
    fhir_resources = ("Appointment", "AppointmentResponse")
    patient = ForeignKey(User, on_delete=PROTECT)
    appointment_type = ForeignKey(AppointmentType, on_delete=PROTECT)
    preferred_clinician = ForeignKey(
        ClinicianProfile, null=True, blank=True, on_delete=PROTECT, related_name="+"
    )
    earliest_at = DateTimeField()
    latest_at = DateTimeField()
    status = CharField(max_length=20, choices=choices_of(WaitlistStatus))
    offered_appointment = ForeignKey(
        Appointment, null=True, blank=True, on_delete=PROTECT, related_name="+"
    )

    class Meta:
        verbose_name_plural = "waitlist entries"
        constraints = [
            ends_after_start("waitlistentry", "earliest_at", "latest_at"),
            one_of("waitlistentry", "status", WaitlistStatus),
            check(
                "waitlistentry_offer_matches_status",
                (Q(status=WaitlistStatus.WAITING) & Q(offered_appointment__isnull=True))
                | (Q(status=WaitlistStatus.OFFERED) & Q(offered_appointment__isnull=False))
                | Q(status__in=[WaitlistStatus.BOOKED, WaitlistStatus.EXPIRED]),
                "a WAITING entry has no offered appointment and an OFFERED entry has one",
            ),
            UniqueConstraint(
                fields=["offered_appointment"],
                condition=Q(status=WaitlistStatus.OFFERED),
                name="waitlistentry_one_offer_per_appointment",
                violation_error_message="that appointment is already offered to someone",
            ),
        ]


class Notification(Versioned):
    fhir_resources = ("Communication",)
    # A default, not auto_now_add, so the creation time can be set for imported or test rows.
    created_at = DateTimeField(default=timezone.now)
    recipient = ForeignKey(User, on_delete=PROTECT)
    kind = CharField(max_length=30, choices=NotificationKind)
    title = CharField(max_length=TITLE_MAXIMUM)
    body = TextField(blank=True, default="")
    appointment = ForeignKey(Appointment, null=True, blank=True, on_delete=PROTECT)
    waitlist_entry = ForeignKey(WaitlistEntry, null=True, blank=True, on_delete=PROTECT)
    read_at = DateTimeField(null=True, blank=True)
    # Created and not yet mailed; a bool, not a sent-at time, so old rows are never mailed.
    email_pending = BooleanField(default=False)

    class Meta:
        indexes = [
            Index(
                fields=["created_at"],
                condition=Q(email_pending=True),
                name="notification_email_pending",
            )
        ]
        constraints = [
            one_of("notification", "kind", NotificationKind),
            not_blank("notification", "title"),
            UniqueConstraint(
                fields=["appointment"],
                condition=Q(kind=NotificationKind.APPOINTMENT_REMINDER),
                name="notification_one_reminder_per_appointment",
                violation_error_message="the appointment already has a reminder",
            ),
        ]
