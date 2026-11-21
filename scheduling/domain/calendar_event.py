"""RFC 5545 event text. No description: the reason and notes never leave the system."""

from dataclasses import dataclass
from datetime import datetime

LINE_BREAK = "\r\n"
MAXIMUM_LINE_OCTETS = 75


@dataclass(frozen=True)
class CalendarEvent:
    uid: str
    starts_at: datetime
    ends_at: datetime
    stamped_at: datetime
    summary: str
    location: str


def build_calendar_text(event: CalendarEvent) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DrLibre//Booking//EN",
        "BEGIN:VEVENT",
        f"UID:{event.uid}",
        f"DTSTAMP:{_utc_text(event.stamped_at)}",
        f"DTSTART:{_utc_text(event.starts_at)}",
        f"DTEND:{_utc_text(event.ends_at)}",
        f"SUMMARY:{_escape(event.summary)}",
        f"LOCATION:{_escape(event.location)}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "".join(f"{folded}{LINE_BREAK}" for line in lines for folded in _fold(line))


def _utc_text(moment: datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return escaped.replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    parts: list[str] = []
    current = ""
    for character in line:
        limit = MAXIMUM_LINE_OCTETS - (1 if parts else 0)
        if len((current + character).encode()) > limit:
            parts.append(current)
            current = character
        else:
            current += character
    parts.append(current)
    return [parts[0], *(f" {part}" for part in parts[1:])]
