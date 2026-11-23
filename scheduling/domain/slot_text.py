"""The text of one slot in the hospital's zone, as it reads on screen."""

from datetime import datetime
from zoneinfo import ZoneInfo


def slot_visible_text(starts_at: datetime, time_zone: str) -> str:
    local = starts_at.astimezone(ZoneInfo(time_zone))
    return f"{local:%a} {local.day} {local:%b}, {local:%H:%M}"
