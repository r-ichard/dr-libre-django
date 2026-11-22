"""Addresses and wording shared by the booking pages. No personal detail is put in an address:
the slot and the provider are public, the rest travels by POST or is addressed by the hold."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from urllib.parse import urlencode
from uuid import UUID
from zoneinfo import ZoneInfo

from django.http import Http404
from django.views import View

from scheduling.domain.request_limits import day_in_range, instant_in_range
from scheduling.models import Hospital

START_PATH = "/"
PATIENT_PATH = "/patient/"


@dataclass(frozen=True)
class SlotRequest:
    type_id: UUID
    provider_id: UUID | None
    starts_at: datetime


def times_href(type_id: UUID, provider_id: UUID | None, week: date | None = None) -> str:
    query = {"provider": str(provider_id)} if provider_id else {}
    if week is not None:
        query["week"] = week.isoformat()
    suffix = f"?{urlencode(query)}" if query else ""
    return f"/book/{type_id}{suffix}"


def details_href(type_id: UUID, provider_id: UUID | None, starts_at: datetime) -> str:
    query = {"provider": str(provider_id)} if provider_id else {}
    query["starts_at"] = starts_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"/book/{type_id}/details?{urlencode(query, safe=':')}"


def code_href(hold_id: UUID) -> str:
    return f"/book/holds/{hold_id}/code"


def resend_href(hold_id: UUID) -> str:
    return f"/book/holds/{hold_id}/resend"


def confirmation_href(appointment_id: UUID) -> str:
    return f"/appointments/{appointment_id}/confirmation"


def path_uuid(view: View, name: str) -> UUID:
    return UUID(str(view.kwargs[name]))


def provider_from(raw: str) -> UUID | None:
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError as unreadable:
        raise Http404 from unreadable


def instant_from(raw: str) -> datetime | None:
    try:
        instant = datetime.fromisoformat(raw)
        utc = instant.astimezone(UTC) if instant.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None
    return utc if utc is not None and instant_in_range(utc) else None


def is_instant(raw: str) -> bool:
    """A value with a date, time and offset, in range or not."""
    try:
        return datetime.fromisoformat(raw).utcoffset() is not None
    except ValueError:
        return False


def week_from(raw: str) -> date | None:
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        return None
    return day if day_in_range(day) else None


def day_label(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B %Y}"


def clock_label(instant: datetime, time_zone: ZoneInfo) -> str:
    return f"{instant.astimezone(time_zone):%H:%M}"


def address_of(hospital: Hospital) -> str:
    return f"{hospital.street_address}, {hospital.postal_code} {hospital.city}"
