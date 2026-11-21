"""Task 17, patients: the clinician's own patients with a name search. The use case builds the
set from the clinician's appointments, so the search text can only narrow it."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse

from scheduling.use_cases.clinician_patients import patients_of
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.clinician_support import PATIENTS_PATH, ClinicianPage

NO_VISIT = "None"
QUERY_MAXIMUM = 100


def _day(moment: datetime | None, zone: ZoneInfo) -> str:
    return NO_VISIT if moment is None else f"{moment.astimezone(zone):%d %b %Y}"


class PatientsPage(ClinicianPage):
    template_name = "clinician/patients.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        zone = ZoneInfo(profile.department.hospital.time_zone)
        query = request.GET.get("q", "").strip()[:QUERY_MAXIMUM]
        found = patients_of(profile, query, current_request_context().now)
        rows = [
            {
                "name": row.name,
                "phone": row.phone,
                "last_visit": _day(row.last_visit, zone),
                "next_visit": _day(row.next_visit, zone),
            }
            for row in found
        ]
        context = {"rows": rows, "query": query, "action": PATIENTS_PATH}
        return self.page(request, context)
