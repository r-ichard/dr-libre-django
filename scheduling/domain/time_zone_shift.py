"""Which appointments show another local time after a zone change."""

from collections.abc import Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

from scheduling.domain.written_moment import written_moment


def shifted_starts(
    starts: Sequence[datetime], old_zone: ZoneInfo, new_zone: ZoneInfo
) -> list[datetime]:
    return [start for start in starts if _wall(start, old_zone) != _wall(start, new_zone)]


def zone_change_sentence(
    shifted: Sequence[datetime], old_zone: ZoneInfo, new_zone: ZoneInfo
) -> str:
    """The admin's warning, with the first shifted start as the example; `shifted` is not empty."""
    example = shifted[0]
    count = len(shifted)
    plural = "" if count == 1 else "s"
    return (
        f"{count} upcoming appointment{plural} will show another local time. For example, "
        f"{written_moment(example, old_zone)} will read {written_moment(example, new_zone)}."
    )


def _wall(start: datetime, zone: ZoneInfo) -> datetime:
    return start.astimezone(zone).replace(tzinfo=None)
