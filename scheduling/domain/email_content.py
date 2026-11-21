"""Section 7.6: the text of a patient email. The input has no field for a reason or a note, so
neither can reach a message."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class EmailSubject:
    title: str
    sign_in_url: str
    starts_at: datetime | None = None
    time_zone: ZoneInfo = ZoneInfo("UTC")
    hospital_name: str | None = None
    provider_name: str | None = None


@dataclass(frozen=True)
class EmailText:
    subject: str
    body: str


def patient_email(content: EmailSubject) -> EmailText:
    details = []
    if content.starts_at is not None:
        local = content.starts_at.astimezone(content.time_zone)
        details.append(f"When: {local:%Y-%m-%d} at {local:%H:%M} ({content.time_zone.key})")
    if content.hospital_name is not None:
        details.append(f"Where: {content.hospital_name}")
    if content.provider_name is not None:
        details.append(f"Provider: {content.provider_name}")
    lines = [f"{content.title}.", ""]
    if details:
        lines += [*details, ""]
    lines.append(f"Sign in to see your appointments: {content.sign_in_url}")
    return EmailText(content.title, "\n".join(lines))
