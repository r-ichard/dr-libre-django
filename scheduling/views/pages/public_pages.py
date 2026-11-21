"""Pages open to everyone: the component style page that exists only in DEBUG."""

from django.http import HttpRequest, HttpResponse

from scheduling.domain.calendar_grid import HOUR_LABELS
from scheduling.views.pages.page_view import PageView
from scheduling.views.pages.time_grid import axis_rows

SPECIALTIES = [("cardiology", "Cardiology"), ("dermatology", "Dermatology")]
SAMPLE_ERRORS = [
    {"target": "id_sample_error", "message": "Enter a date of birth."},
    {"target": "id_sample_select_error", "message": "Choose a hospital."},
]
SPECIMEN_ROW = {
    "href": "#",
    "patient": "Jane Doe",
    "time": "09:00 to 09:30",
    "type_name": "Check-up",
    "room": "Room 3",
    "badge_kind": "information",
    "badge_text": "Booked",
    "forms": [{"action": "#", "label": "Check in"}],
    "cancel_href": "#",
    "reschedule_href": "#",
    "return_date": "2030-01-07",
}
SPECIMEN_HISTORY = [{"time": "07 Jan 2030, 09:02", "label": "Checked in", "actor": "Dr Okafor"}]
SPECIMEN_COLUMNS = [
    {
        "heading": "Mon 7 Jan",
        "spoken": "Monday 7 January 2030",
        "inside": [
            {
                "lines": ("09:00 to 09:30", "Check-up", "Jane Doe"),
                "href": "#",
                "badge": ("information", "Booked"),
                "classes": "time-grid-at-5 time-grid-span-1",
            },
            {
                "lines": ("11:00 to 12:00", "Occupied"),
                "href": "",
                "badge": None,
                "classes": "time-grid-at-9 time-grid-span-2 time-grid-occupied",
            },
        ],
        "outside": [],
        "outside_title": "Outside 07:00 to 19:00",
    }
]


class StylePage(PageView):
    template_name = "style.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return self.page(
            request,
            {
                "specialties": SPECIALTIES,
                "summary_errors": SAMPLE_ERRORS,
                "specimen_row": SPECIMEN_ROW,
                "specimen_history": SPECIMEN_HISTORY,
                "specimen_columns": SPECIMEN_COLUMNS,
                "specimen_axis": axis_rows(),
                "specimen_axis_end": HOUR_LABELS[-1],
            },
        )
