"""Section 7.6: the text of a patient email. The input has no field for a reason or a note, so
neither can reach a message."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class EmailSubject:
    title: str
    starts_at: datetime
    time_zone: ZoneInfo
    hospital_name: str
    provider_name: str
    sign_in_url: str


@dataclass(frozen=True)
class EmailText:
    subject: str
    body: str


def patient_email(content: EmailSubject) -> EmailText:
    local = content.starts_at.astimezone(content.time_zone)
    lines = [
        f"{content.title}.",
        "",
        f"When: {local:%Y-%m-%d} at {local:%H:%M} ({content.time_zone.key})",
        f"Where: {content.hospital_name}",
        f"Provider: {content.provider_name}",
        "",
        f"Sign in to see your appointments: {content.sign_in_url}",
    ]
    return EmailText(content.title, "\n".join(lines))
