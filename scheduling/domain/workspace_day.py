"""Section 9.1: the local day of a hospital, hour groups and the tiles of the day."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from scheduling.domain.appointment_status import is_active
from scheduling.domain.vocabulary import AppointmentStatus


def local_day_bounds(day: date, time_zone: str) -> tuple[datetime, datetime]:
    """Midnight to midnight in the zone, as UTC; a clock change makes it 23 or 25 hours."""
    zone = ZoneInfo(time_zone)
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return start.astimezone(UTC), end.astimezone(UTC)


def group_by_local_hour(starts: Iterable[datetime], time_zone: str) -> dict[int, list[datetime]]:
    zone = ZoneInfo(time_zone)
    groups: dict[int, list[datetime]] = {}
    for starts_at in sorted(starts):
        groups.setdefault(starts_at.astimezone(zone).hour, []).append(starts_at)
    return dict(sorted(groups.items()))


@dataclass(frozen=True)
class DayTiles:
    active: int
    cancelled: int
    completed: int
    no_show: int


def day_tiles(statuses: Iterable[AppointmentStatus]) -> DayTiles:
    listed = list(statuses)
    return DayTiles(
        active=sum(
            1 for status in listed if is_active(status) and status != AppointmentStatus.COMPLETED
        ),
        cancelled=listed.count(AppointmentStatus.CANCELLED),
        completed=listed.count(AppointmentStatus.COMPLETED),
        no_show=listed.count(AppointmentStatus.NO_SHOW),
    )
