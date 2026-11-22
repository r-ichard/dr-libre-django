"""Task 16: what every clinician page shares: the role guard, the clinician's own profile, the
record rule of one appointment, and the words of a status."""

from django.http import Http404, HttpRequest, HttpResponse

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.vocabulary import Role
from scheduling.models import Appointment, ClinicianProfile
from scheduling.use_cases.clinician_agenda import clinician_profile_of
from scheduling.use_cases.clinician_appointment import own_appointment_of_clinician
from scheduling.views.pages.booking_links import path_uuid
from scheduling.views.pages.page_view import PageView, render_page
from scheduling.views.pages.status_words import STAFF_APPOINTMENT_BADGES

TODAY_PATH = "/clinician/"
CALENDAR_PATH = "/clinician/calendar"
APPOINTMENT_PATH = "/clinician/appointments"
AVAILABILITY_PATH = "/clinician/availability"
TIME_OFF_PATH = "/clinician/time-off"
PATIENTS_PATH = "/clinician/patients"
ROOMS_PATH = "/clinician/rooms"

# The clinician's word for a missed visit is the status name; the patient's is "Missed".
CLINICIAN_BADGES = STAFF_APPOINTMENT_BADGES


def appointment_path(appointment_id: object) -> str:
    return f"{APPOINTMENT_PATH}/{appointment_id}"


class ClinicianPage(PageView):
    allowed_roles = frozenset({Role.CLINICIAN})

    def profile_or_refusal(self, request: HttpRequest) -> ClinicianProfile | HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        profile = clinician_profile_of(self.user)
        if profile is None:
            return render_page(request, "clinician/no_profile.html", signed_in_user=self.user)
        return profile

    def appointment_or_refusal(self, request: HttpRequest) -> Appointment | HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = own_appointment_of_clinician(path_uuid(self, "appointment_id"), self.user)
        if isinstance(found, Failure):
            return self.refusal_of(request, found)
        return found.value

    def refusal_of(self, request: HttpRequest, failure: Failure) -> HttpResponse:
        """Missing is a 404; someone else's shows the one sentence and nothing of the record."""
        if failure.code == FailureCode.NOT_FOUND:
            raise Http404
        return render_page(
            request, "clinician/not_yours.html", {"today_path": TODAY_PATH},
            status=403, signed_in_user=self.user,
        )  # fmt: skip
