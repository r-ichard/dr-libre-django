"""Task 17, rooms: one day of the department's active rooms on the shared time grid. The
use case decides what a cell may say; this view only formats it."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse

from scheduling.domain.calendar_grid import HOUR_LABELS
from scheduling.domain.workspace_day import local_day_bounds
from scheduling.use_cases.clinician_rooms import room_day
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.booking_links import clock_label, week_from
from scheduling.views.pages.clinician_support import ROOMS_PATH, ClinicianPage, appointment_path
from scheduling.views.pages.time_grid import GridItem, axis_rows, grid_column


def day_href(day: date) -> str:
    return f"{ROOMS_PATH}?date={day.isoformat()}"


class RoomsPage(ClinicianPage):
    template_name = "clinician/rooms.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        time_zone = profile.department.hospital.time_zone
        zone = ZoneInfo(time_zone)
        today = current_request_context().now.astimezone(zone).date()
        day = week_from(request.GET.get("date", "")) or today
        window = local_day_bounds(day, time_zone)
        columns = []
        for entry in room_day(profile, day):
            items = [
                GridItem(
                    cell.starts_at,
                    cell.ends_at,
                    (
                        f"{clock_label(cell.starts_at, zone)} to {clock_label(cell.ends_at, zone)}",
                        cell.label,
                    ),
                    "" if cell.appointment_id is None else appointment_path(cell.appointment_id),
                    "time-grid-occupied" if cell.appointment_id is None else "",
                    None,
                )
                for cell in entry.cells
            ]
            heading = entry.room.name
            columns.append(grid_column(heading, f"Room {heading}", items, window, time_zone))
        context = {
            "day_text": f"{day:%A} {day.day} {day:%B %Y}",
            "time_zone": time_zone,
            "previous_href": day_href(day - timedelta(days=1)),
            "today_href": day_href(today),
            "next_href": day_href(day + timedelta(days=1)),
            "columns": columns,
            "axis": axis_rows(),
            "axis_end": HOUR_LABELS[-1],
        }
        return self.page(request, context)
