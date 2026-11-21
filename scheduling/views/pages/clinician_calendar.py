"""Task 16, calendar: a week of the clinician's active appointments and time off. The markup is
a list of days of blocks, so it reads in order for a screen reader and at 375 px; wide screens
lay the same lists out as a grid with static row classes."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse
from django.utils.cache import patch_cache_control

from scheduling.domain.booking_week import next_week_start, previous_week_start
from scheduling.domain.calendar_grid import place_in_grid
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.domain.workspace_day import local_day_bounds
from scheduling.models import Appointment, ClinicianProfile, TimeOff
from scheduling.use_cases.clinician_agenda import (
    clinician_profile_of,
    department_types,
    week_appointments,
    week_time_off,
)
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.booking_links import clock_label, day_label, week_from
from scheduling.views.pages.clinician_support import (
    CALENDAR_PATH,
    CLINICIAN_BADGES,
    ClinicianPage,
    appointment_path,
)

COLOUR_PATTERN = re.compile(r"#[0-9a-f]{6}")
COLOUR_CACHE_SECONDS = 300
DAYS_PER_WEEK = 7
OUTSIDE_GRID = "Outside 07:00 to 19:00"


def week_href(week_start: date) -> str:
    return f"{CALENDAR_PATH}?week={week_start.isoformat()}"


@dataclass(frozen=True)
class Block:
    """One entry of a day: appointment or time off, with the span it covers that day."""

    starts_at: datetime
    ends_at: datetime
    text: str
    href: str
    colour_class: str
    badge: tuple[str, str] | None


class CalendarPage(ClinicianPage):
    template_name = "clinician/calendar.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        time_zone = profile.department.hospital.time_zone
        today = current_request_context().now.astimezone(ZoneInfo(time_zone)).date()
        asked = week_from(request.GET.get("week", "")) or today
        monday = asked - timedelta(days=asked.weekday())
        blocks = _blocks(profile, monday)
        days = [_day(monday + timedelta(days=offset), blocks, time_zone) for offset in range(7)]
        last_day = monday + timedelta(days=DAYS_PER_WEEK - 1)
        context = {
            "days": days,
            "week_label": f"{day_label(monday)} to {day_label(last_day)}",
            "previous_href": week_href(previous_week_start(monday)),
            "next_href": week_href(next_week_start(monday)),
            "time_zone": time_zone,
        }
        return self.page(request, context)


def _blocks(profile: ClinicianProfile, monday: date) -> list[Block]:
    zone = ZoneInfo(profile.department.hospital.time_zone)
    appointments = [_appointment_block(row, zone) for row in week_appointments(profile, monday)]
    off = [_time_off_block(row, zone) for row in week_time_off(profile, monday)]
    return sorted([*appointments, *off], key=lambda block: block.starts_at)


def _appointment_block(row: Appointment, zone: ZoneInfo) -> Block:
    room = f", {row.room.name}" if row.room else ""
    span = f"{clock_label(row.starts_at, zone)} to {clock_label(row.ends_at, zone)}"
    return Block(
        row.starts_at,
        row.ends_at,
        f"{span}, {row.appointment_type.name}, {row.patient.full_name}{room}",
        appointment_path(row.pk),
        f"type-colour--{row.appointment_type_id.hex}",
        CLINICIAN_BADGES[AppointmentStatus(row.status)],
    )


def _time_off_block(row: TimeOff, zone: ZoneInfo) -> Block:
    reason = f", {row.reason}" if row.reason else ""
    span = f"{clock_label(row.starts_at, zone)} to {clock_label(row.ends_at, zone)}"
    return Block(row.starts_at, row.ends_at, f"{span}, Time off{reason}", "", "cal-off", None)


def _day(day: date, blocks: list[Block], time_zone: str) -> dict[str, object]:
    day_start, day_end = local_day_bounds(day, time_zone)
    inside: list[dict[str, object]] = []
    outside: list[dict[str, object]] = []
    for block in blocks:
        if block.starts_at >= day_end or block.ends_at <= day_start:
            continue
        placement = place_in_grid(
            max(block.starts_at, day_start), min(block.ends_at, day_end), time_zone
        )
        item = {"text": block.text, "href": block.href, "badge": block.badge}
        if placement is None:
            outside.append({**item, "classes": block.colour_class})
        else:
            grid = f"cal-row-{placement.first_row} cal-span-{placement.span}"
            inside.append({**item, "classes": f"{grid} {block.colour_class}"})
    return {
        "heading": f"{day:%a} {day.day} {day:%b}",
        "spoken": day_label(day),
        "inside": inside,
        "outside": outside,
        "outside_title": OUTSIDE_GRID,
    }


class ColoursPage(ClinicianPage):
    """The stored colour of each type as a CSS rule: inline style is forbidden, a same-origin
    stylesheet is not. It holds no patient data, so a short private cache is fine."""

    def get(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        profile = clinician_profile_of(self.user)
        rules = [
            f".type-colour--{row.pk.hex} {{ --type-colour: {row.colour}; }}"
            for row in (department_types(profile) if profile else [])
            if COLOUR_PATTERN.fullmatch(row.colour)
        ]
        response = HttpResponse("\n".join(rules) + "\n", content_type="text/css")
        patch_cache_control(response, private=True, max_age=COLOUR_CACHE_SECONDS)
        return response
