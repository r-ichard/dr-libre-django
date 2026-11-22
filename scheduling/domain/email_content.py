"""Section 7.6: the text of a patient email. The input has no field for a reason or a note, so
neither can reach a message."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from scheduling.domain.written_moment import written_moment


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
        details.append(f"When: {written_moment(content.starts_at, content.time_zone)}")
    if content.hospital_name is not None:
        details.append(f"Where: {content.hospital_name}")
    if content.provider_name is not None:
        details.append(f"Provider: {content.provider_name}")
    lines = [f"{content.title}.", ""]
    if details:
        lines += [*details, ""]
    lines.append(f"Sign in to see your appointments: {content.sign_in_url}")
    return EmailText(content.title, "\n".join(lines))


def verification_code_email(code: str, valid_minutes: int) -> EmailText:
    """Only the code: nothing in this message signs the reader in or opens a page."""
    body = (
        f"Your DrLibre booking code is {code}.\n"
        "\n"
        f"It is valid for {valid_minutes} minutes. Enter it on the booking page to finish "
        "your booking.\n"
        "\n"
        "If you did not ask for this code, ignore this message."
    )
    return EmailText("Your DrLibre booking code", body)


def sign_in_link_email(link_url: str, valid_minutes: int) -> EmailText:
    """The only message of the product that signs its reader in."""
    body = (
        "Use this link to sign in to DrLibre:\n"
        "\n"
        f"{link_url}\n"
        "\n"
        f"The link is valid for {valid_minutes} minutes and works only once. Opening it shows "
        "a page with a Continue button; you are signed in when you press it.\n"
        "\n"
        "If you did not ask for this link, ignore this message."
    )
    return EmailText("Your DrLibre sign-in link", body)
