"""What blocks a clinician inside a window: time off, booked appointments, live holds."""

from collections.abc import Collection
from datetime import datetime, timedelta
from uuid import UUID

from scheduling.domain.appointment_status import ACTIVE_STATUSES
from scheduling.domain.free_slots import BusyInterval, TimeRange
from scheduling.models import Appointment, BookingHold, TimeOff

type Blocks = tuple[list[BusyInterval], list[BusyInterval], list[BusyInterval]]


def busy_intervals(
    clinician_ids: Collection[UUID], window: TimeRange, buffer: timedelta, now: datetime
) -> dict[UUID, Blocks]:
    blocks: dict[UUID, Blocks] = {key: ([], [], []) for key in clinician_ids}
    reaching = {"starts_at__lt": window.ends_at, "clinician_id__in": clinician_ids}
    earliest_end = window.starts_at - buffer
    for off in TimeOff.objects.filter(ends_at__gt=window.starts_at, **reaching):
        blocks[off.clinician_id][0].append(BusyInterval(off.starts_at, off.ends_at))
    booked = Appointment.objects.filter(
        status__in=ACTIVE_STATUSES, ends_at__gt=earliest_end, **reaching
    )
    for item in booked:
        blocks[item.clinician_id][1].append(BusyInterval(item.starts_at, item.ends_at))
    for hold in BookingHold.objects.filter(
        expires_at__gt=now, ends_at__gt=earliest_end, **reaching
    ):
        blocks[hold.clinician_id][2].append(BusyInterval(hold.starts_at, hold.ends_at))
    return blocks
