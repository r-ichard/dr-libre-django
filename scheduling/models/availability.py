from django.db.models import (
    PROTECT,
    CharField,
    DateField,
    DateTimeField,
    F,
    ForeignKey,
    Q,
    SmallIntegerField,
    TimeField,
)

from scheduling.models.base import (
    Versioned,
    between,
    check,
    ends_after_start,
    whole_minutes,
)
from scheduling.models.organisation import Room
from scheduling.models.people import ClinicianProfile

WEEKDAY_MONDAY = 0
WEEKDAY_SUNDAY = 6
SLOT_STEP_MINIMUM = 5
SLOT_STEP_MAXIMUM = 240


class AvailabilityRule(Versioned):
    fhir_resources = ("Schedule",)
    clinician = ForeignKey(ClinicianProfile, on_delete=PROTECT)
    weekday = SmallIntegerField()
    start_time = TimeField()
    end_time = TimeField()
    slot_step_minutes = SmallIntegerField(default=15)
    room = ForeignKey(Room, null=True, blank=True, on_delete=PROTECT)
    valid_from = DateField()
    valid_to = DateField(null=True, blank=True)

    class Meta:
        constraints = [
            between("availabilityrule", "weekday", WEEKDAY_MONDAY, WEEKDAY_SUNDAY),
            ends_after_start("availabilityrule", "start_time", "end_time"),
            whole_minutes("availabilityrule", "start_time"),
            whole_minutes("availabilityrule", "end_time"),
            between("availabilityrule", "slot_step_minutes", SLOT_STEP_MINIMUM, SLOT_STEP_MAXIMUM),
            check(
                "availabilityrule_valid_to_not_before_valid_from",
                Q(valid_to__isnull=True) | Q(valid_to__gte=F("valid_from")),
                "valid_to must not be before valid_from",
            ),
        ]


class TimeOff(Versioned):
    fhir_resources = ("PractitionerRole",)
    clinician = ForeignKey(ClinicianProfile, on_delete=PROTECT)
    starts_at = DateTimeField()
    ends_at = DateTimeField()
    reason = CharField(max_length=200, blank=True, default="")

    class Meta:
        verbose_name_plural = "time off"
        constraints = [ends_after_start("timeoff", "starts_at", "ends_at")]
