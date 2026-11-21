"""Pages open to everyone: the component style page that exists only in DEBUG."""

from django.http import HttpRequest, HttpResponse

from scheduling.views.pages.page_view import PageView

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
SPECIMEN_DAYS = [
    {
        "heading": "Mon 7 Jan",
        "spoken": "Monday 7 January 2030",
        "inside": [
            {
                "text": "09:00 to 09:30, Check-up, Jane Doe",
                "href": "#",
                "badge": ("information", "Booked"),
                "classes": "cal-row-5 cal-span-1",
            }
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
                "specimen_days": SPECIMEN_DAYS,
            },
        )
