"""Task 14: the first two booking steps, service and provider, leading into the times step."""

from django.http import Http404, HttpRequest, HttpResponse

from scheduling.use_cases.booking_page_data import bookable_services, type_providers
from scheduling.views.pages.booking_links import path_uuid, times_href
from scheduling.views.pages.booking_summary import duration_label
from scheduling.views.pages.page_view import PageView


class ServicePage(PageView):
    template_name = "booking/service.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        hospitals = [
            {
                "name": hospital.name,
                "departments": [
                    {
                        "name": department.name,
                        "types": [
                            {
                                "name": appointment_type.name,
                                "duration": duration_label(appointment_type.duration_minutes),
                                "href": f"/book/{appointment_type.pk}/provider",
                            }
                            for appointment_type in department.types
                        ],
                    }
                    for department in hospital.departments
                ],
            }
            for hospital in bookable_services()
        ]
        return self.page(request, {"hospitals": hospitals})


class ProviderChoicePage(PageView):
    template_name = "booking/provider.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        type_id = path_uuid(self, "appointment_type_id")
        loaded = type_providers(type_id)
        if loaded is None:
            raise Http404
        appointment_type, clinicians = loaded
        context = {
            "type_name": appointment_type.name,
            "first_available_href": times_href(type_id, None),
            "providers": [
                {
                    "name": f"{clinician.title} {clinician.user.full_name}",
                    "specialty": clinician.specialty.name,
                    "href": times_href(type_id, clinician.pk),
                }
                for clinician in clinicians
            ],
        }
        return self.page(request, context)
