"""Section 9.3: the database refuses overlapping rules of one clinician and a repeated period."""

from datetime import time

import pytest

from scheduling.models import AvailabilityRule, TimeOff
from scheduling.models.builders import ENDS_AT, STARTS_AT, make, refuses

pytestmark = pytest.mark.django_db

MONDAY = 1


def _rule(clinician: object, start: time, end: time, weekday: int = MONDAY) -> None:
    make("AvailabilityRule", clinician=clinician, weekday=weekday, start_time=start, end_time=end)


def rejects_overlapping_rules_in_database() -> None:
    clinician = make("ClinicianProfile")
    _rule(clinician, time(9, 0), time(12, 0))

    refuses(
        "AvailabilityRule",
        clinician=clinician,
        weekday=MONDAY,
        start_time=time(11, 59),
        end_time=time(13, 0),
    )

    assert AvailabilityRule.objects.filter(clinician_id=clinician.pk).count() == 1


def returns_inserts_touching_rules_in_database() -> None:
    clinician = make("ClinicianProfile")
    _rule(clinician, time(9, 0), time(12, 0))

    _rule(clinician, time(12, 0), time(15, 0))

    assert AvailabilityRule.objects.filter(clinician_id=clinician.pk).count() == 2


def returns_inserts_same_times_for_other_weekday_and_other_clinician() -> None:
    clinician = make("ClinicianProfile")
    _rule(clinician, time(9, 0), time(12, 0))

    _rule(clinician, time(9, 0), time(12, 0), weekday=2)
    _rule(make("ClinicianProfile"), time(9, 0), time(12, 0))

    assert AvailabilityRule.objects.count() == 3


def rejects_identical_time_off_in_database() -> None:
    clinician = make("ClinicianProfile")
    make("TimeOff", clinician=clinician, starts_at=STARTS_AT, ends_at=ENDS_AT)

    refuses("TimeOff", clinician=clinician, starts_at=STARTS_AT, ends_at=ENDS_AT)

    assert TimeOff.objects.filter(clinician_id=clinician.pk).count() == 1


def returns_inserts_identical_time_off_for_other_clinician() -> None:
    make("TimeOff", clinician=make("ClinicianProfile"), starts_at=STARTS_AT, ends_at=ENDS_AT)

    make("TimeOff", clinician=make("ClinicianProfile"), starts_at=STARTS_AT, ends_at=ENDS_AT)

    assert TimeOff.objects.count() == 2
