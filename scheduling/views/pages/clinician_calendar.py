"""Task 16, calendar: a week of the clinician's active appointments and time off. The markup is
a list of days of blocks, so it reads in order for a screen reader and at 375 px; wide screens
lay the same lists out as a grid with static row classes."""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse
from django.utils.cache import patch_cache_control

from scheduling.domain.booking_week import next_week_start, previous_week_start
from scheduling.domain.calendar_grid import HOUR_LABELS
from scheduling.domain.period_days import cut_into_days
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
from scheduling.views.pages.time_grid import GridItem, axis_rows, grid_column

COLOUR_PATTERN = re.compile(r"#[0-9a-f]{6}")
COLOUR_CACHE_SECONDS = 300
DAYS_PER_WEEK = 7


def week_href(week_start: date) -> str:
    return f"{CALENDAR_PATH}?week={week_start.isoformat()}"


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
        week_days = [monday + timedelta(days=offset) for offset in range(DAYS_PER_WEEK)]
        off = week_time_off(profile, monday)
        days = [
            _day(day, blocks + _time_off_items(off, day, time_zone), time_zone) for day in week_days
        ]
        last_day = monday + timedelta(days=DAYS_PER_WEEK - 1)
        context = {
            "columns": days,
            "axis": axis_rows(),
            "axis_end": HOUR_LABELS[-1],
            "week_label": f"{day_label(monday)} to {day_label(last_day)}",
            "previous_href": week_href(previous_week_start(monday)),
            "next_href": week_href(next_week_start(monday)),
            "time_zone": time_zone,
        }
        return self.page(request, context)


def _blocks(profile: ClinicianProfile, monday: date) -> list[GridItem]:
    zone = ZoneInfo(profile.department.hospital.time_zone)
    appointments = [_appointment_item(row, zone) for row in week_appointments(profile, monday)]
    return sorted(appointments, key=lambda item: item.starts_at)


def _span_text(starts_at: datetime, ends_at: datetime, zone: ZoneInfo) -> str:
    return f"{clock_label(starts_at, zone)} to {clock_label(ends_at, zone)}"


def _appointment_item(row: Appointment, zone: ZoneInfo) -> GridItem:
    """Time, type and patient; the room and the rest are on the appointment page."""
    return GridItem(
        row.starts_at,
        row.ends_at,
        (
            _span_text(row.starts_at, row.ends_at, zone),
            row.appointment_type.name,
            row.patient.full_name,
        ),
        appointment_path(row.pk),
        f"type-colour--{row.appointment_type_id.hex}",
        CLINICIAN_BADGES[AppointmentStatus(row.status)],
    )


def _time_off_items(rows: list[TimeOff], day: date, time_zone: str) -> list[GridItem]:
    """The part of each period inside this day; the text keeps the real start and end."""
    zone = ZoneInfo(time_zone)
    items: list[GridItem] = []
    for row in rows:
        for part in cut_into_days(row.starts_at, row.ends_at, [day], time_zone):
            if part.starts_at == row.starts_at and part.ends_at == row.ends_at:
                when = _span_text(row.starts_at, row.ends_at, zone)
            else:
                when = f"{_dated_clock(row.starts_at, zone)} to {_dated_clock(row.ends_at, zone)}"
            lines = (when, "Time off") + ((row.reason,) if row.reason else ())
            items.append(GridItem(part.starts_at, part.ends_at, lines, "", "time-grid-off", None))
    return items


def _dated_clock(instant: datetime, zone: ZoneInfo) -> str:
    local = instant.astimezone(zone)
    return f"{local:%a} {local.day} {local:%b} {local:%H:%M}"


def _day(day: date, items: list[GridItem], time_zone: str) -> dict[str, object]:
    window = local_day_bounds(day, time_zone)
    return grid_column(f"{day:%a} {day.day} {day:%b}", day_label(day), items, window, time_zone)


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
