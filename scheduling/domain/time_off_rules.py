"""Section 9.3: time off needs an end after its start, a short reason and a new period."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from scheduling.domain.failure import Failure, FieldMessage
from scheduling.domain.text_rules import check_storable_text
from scheduling.domain.vocabulary import AppointmentStatus

REASON_MAXIMUM = 200
FREED_STATUSES: frozenset[str] = frozenset({AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW})


@dataclass(frozen=True)
class PlannedVisit:
    label: str
    starts_at: datetime
    ends_at: datetime
    status: str


def time_off_failures(
    starts_at: datetime,
    ends_at: datetime,
    reason: str,
    existing_periods: Sequence[tuple[datetime, datetime]],
) -> list[FieldMessage]:
    failures: list[FieldMessage] = []
    if ends_at <= starts_at:
        failures.append(FieldMessage("ends_at", "The end must be after the start."))
    unstorable = check_storable_text("reason", reason, single_line=False)
    if isinstance(unstorable, Failure):
        failures += unstorable.field_messages
    elif len(reason.strip()) > REASON_MAXIMUM:
        failures.append(
            FieldMessage("reason", f"The reason is at most {REASON_MAXIMUM} characters.")
        )
    if (starts_at, ends_at) in existing_periods:
        failures.append(FieldMessage("starts_at", "This period is already recorded."))
    return failures


def appointments_inside(
    starts_at: datetime, ends_at: datetime, visits: Sequence[PlannedVisit]
) -> list[PlannedVisit]:
    """Half-open overlap; cancelled and no-show appointments no longer hold the time."""
    return [
        visit
        for visit in visits
        if visit.status not in FREED_STATUSES
        and visit.starts_at < ends_at
        and starts_at < visit.ends_at
    ]
