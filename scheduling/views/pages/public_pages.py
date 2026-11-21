"""Pages open to everyone: the component style page that exists only in DEBUG."""

from django.http import HttpRequest, HttpResponse

from scheduling.views.pages.page_view import PageView

SPECIALTIES = [("cardiology", "Cardiology"), ("dermatology", "Dermatology")]
SAMPLE_ERRORS = [
    {"target": "id_sample_error", "message": "Enter a date of birth."},
    {"target": "id_sample_select_error", "message": "Choose a hospital."},
]


class StylePage(PageView):
    template_name = "style.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return self.page(request, {"specialties": SPECIALTIES, "summary_errors": SAMPLE_ERRORS})
