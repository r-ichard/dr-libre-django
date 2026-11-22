"""Section 13: the appointment list as a CSV file. A POST, so a link on another site cannot make an
admin's browser write audit entries; the filters ride the address and are read like the list's."""

import csv

from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, path
from django.views.decorators.cache import never_cache

from scheduling.domain.failure import Failure
from scheduling.domain.vocabulary import Role
from scheduling.use_cases.admin_appointment_export import export_appointments
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.admin_appointments import EXPORT_PATH, LIST_PATH, asked_filters
from scheduling.views.pages.admin_refusal import admin_refused_page
from scheduling.views.pages.page_view import PageView

BACK_TO_LIST = (LIST_PATH, "Back to the appointments")


class AppointmentExportPage(PageView):
    allowed_roles = frozenset({Role.ADMIN})
    http_method_names = ["post"]

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        filters, _asked = asked_filters(request)
        exported = export_appointments(filters, self.user)
        if isinstance(exported, Failure):
            return admin_refused_page(request, self.user, exported, BACK_TO_LIST)
        day = current_request_context().now.date().isoformat()
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="appointments-{day}.csv"'
        csv.writer(response).writerows(exported.value)
        return response


def admin_appointment_export_routes() -> list[URLPattern]:
    return [path(EXPORT_PATH.removeprefix("/"), never_cache(AppointmentExportPage.as_view()))]
