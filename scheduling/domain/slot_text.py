"""Task 10a: the text of one slot in the hospital's zone, short to read and long to hear."""

from datetime import datetime
from zoneinfo import ZoneInfo


def slot_visible_text(starts_at: datetime, time_zone: str) -> str:
    local = starts_at.astimezone(ZoneInfo(time_zone))
    return f"{local:%a} {local.day} {local:%b}, {local:%H:%M}"


def slot_spoken_text(starts_at: datetime, time_zone: str, provider: str) -> str:
    local = starts_at.astimezone(ZoneInfo(time_zone))
    return f"{local:%A} {local.day} {local:%B %Y} at {local:%H:%M} with {provider}"
