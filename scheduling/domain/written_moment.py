"""Section 16: the one way a moment is written for a person, the zone always named."""

from datetime import datetime
from zoneinfo import ZoneInfo


def written_moment(moment: datetime, zone: ZoneInfo) -> str:
    local = moment.astimezone(zone)
    return f"{local:%A} {local.day} {local:%B %Y}, {local:%H:%M} ({zone.key})"
