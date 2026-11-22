"""Section 10: an admin books for a patient: find them, then the portal's steps with every
active type and no "first available". The patient id rides in the address and is re-read as an
active patient on each step."""

from datetime import UTC, date, datetime
from urllib.parse import urlencode

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import URLPattern, path

from scheduling.domain.failure import Failure
from scheduling.domain.vocabulary import Role
from scheduling.models import User
from scheduling.use_cases.admin_waitlist import active_patient, search_patients
from scheduling.use_cases.booking_page_data import (
    SlotChoice,
    bookable_services,
    slot_choice,
    type_providers,
    week_of_slots,
)
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.views.pages.admin_appointments import LIST_PATH, appointment_path
from scheduling.views.pages.admin_filters import patient_links, search_text, uuid_param
from scheduling.views.pages.admin_notices import admin_redirect
from scheduling.views.pages.admin_refusal import admin_refused_page
from scheduling.views.pages.booking_links import path_uuid, week_from
from scheduling.views.pages.booking_summary import duration_label, slot_summary
from scheduling.views.pages.booking_times import week_strip
from scheduling.views.pages.page_view import PageView
from scheduling.views.pages.patient_reschedule import TIMES_ACTION_TEXT, asked_start

BOOK_PATH = f"{LIST_PATH}/new"
NOT_ONLINE = "not bookable online"


class AdminBookingPage(PageView):
    allowed_roles = frozenset({Role.ADMIN})

    def chosen_patient(self, request: HttpRequest) -> User | HttpResponse:
        """The patient of the address, active, or the search step to choose one again."""
        found = active_patient(uuid_param(request, "patient"))
        return found if found is not None else HttpResponseRedirect(BOOK_PATH)

    def chosen_slot(self, request: HttpRequest) -> tuple[User, SlotChoice] | HttpResponse:
        """Patient, type and provider of the address; a missing provider goes back to the list."""
        patient = self.chosen_patient(request)
        if isinstance(patient, HttpResponse):
            return patient
        type_id = path_uuid(self, "appointment_type_id")
        provider_id = uuid_param(request, "provider")
        if provider_id is None:
            return HttpResponseRedirect(f"{BOOK_PATH}/{type_id}/provider?patient={patient.pk}")
        choice = slot_choice(type_id, provider_id, online_only=False)
        if choice is None:
            raise Http404
        return patient, choice


class PatientStepPage(AdminBookingPage):
    template_name = "admin/book_patient.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        query = search_text(request)
        context = {
            "query": query,
            "found": patient_links(search_patients(query), f"{BOOK_PATH}/service"),
            "search_action": BOOK_PATH,
            "current": "appointments",
        }
        return self.page(request, context)


class ServiceStepPage(AdminBookingPage):
    template_name = "admin/book_service.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        patient = self.chosen_patient(request)
        if isinstance(patient, HttpResponse):
            return patient
        hospitals = [
            {
                "name": hospital.name,
                "departments": [
                    {
                        "name": department.name,
                        "types": [
                            {
                                "name": kind.name,
                                "duration": duration_label(kind.duration_minutes),
                                "note": "" if kind.is_bookable_online else NOT_ONLINE,
                                "href": f"{BOOK_PATH}/{kind.pk}/provider?patient={patient.pk}",
                            }
                            for kind in department.types
                        ],
                    }
                    for department in hospital.departments
                ],
            }
            for hospital in bookable_services(online_only=False)
        ]
        context = {"hospitals": hospitals, "patient": patient, "current": "appointments"}
        return self.page(request, context)


class ProviderStepPage(AdminBookingPage):
    template_name = "admin/book_provider.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        patient = self.chosen_patient(request)
        if isinstance(patient, HttpResponse):
            return patient
        type_id = path_uuid(self, "appointment_type_id")
        loaded = type_providers(type_id, online_only=False)
        if loaded is None:
            raise Http404
        appointment_type, clinicians = loaded
        context = {
            "type_name": appointment_type.name,
            "patient": patient,
            "providers": [
                {
                    "name": f"{clinician.title} {clinician.user.full_name}",
                    "specialty": clinician.specialty.name,
                    "href": f"{BOOK_PATH}/{type_id}/times?"
                    + urlencode({"patient": str(patient.pk), "provider": str(clinician.pk)}),
                }
                for clinician in clinicians
            ],
            "service_href": f"{BOOK_PATH}/service?patient={patient.pk}",
            "current": "appointments",
        }
        return self.page(request, context)


class TimesStepPage(AdminBookingPage):
    template_name = "admin/book_times.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        chosen = self.chosen_slot(request)
        if isinstance(chosen, HttpResponse):
            return chosen
        patient, choice = chosen
        loaded = week_of_slots(
            choice.appointment_type.pk,
            choice.clinician.pk if choice.clinician else None,
            week_from(request.GET.get("week", "")),
            online_only=False,
        )
        if isinstance(loaded, Failure):
            raise Http404
        base = request.path

        def week_href(week_start: date) -> str:
            return f"{base}?{_carried(request, week=week_start.isoformat())}"

        def slot_href(starts_at: datetime) -> str:
            stamp = starts_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            carried = {"patient": str(patient.pk), "starts_at": stamp}
            if choice.clinician:
                carried["provider"] = str(choice.clinician.pk)
            return f"{base.removesuffix('/times')}/review?{urlencode(carried, safe=':')}"

        context = {
            "summary": slot_summary(choice, None),
            "patient": patient,
            "current": "appointments",
            **week_strip(loaded.value, week_href, slot_href),
        }
        return self.page(request, context)


class ReviewStepPage(AdminBookingPage):
    template_name = "admin/book_review.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        chosen = self.chosen_slot(request)
        if isinstance(chosen, HttpResponse):
            return chosen
        patient, choice = chosen
        starts_at = asked_start(request)
        if isinstance(starts_at, Failure):
            return self._refused(request, starts_at)
        context = {
            "summary": slot_summary(choice, starts_at),
            "patient": patient,
            "action": request.get_full_path(),
            "times_path": request.path.removesuffix("/review") + "/times?" + _carried(request),
            "current": "appointments",
        }
        return self.page(request, context)

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        chosen = self.chosen_slot(request)
        if isinstance(chosen, HttpResponse):
            return chosen
        patient, choice = chosen
        starts_at = asked_start(request)
        if isinstance(starts_at, Failure):
            return self._refused(request, starts_at)
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        command = PlacementCommand(
            choice.appointment_type.pk,
            starts_at,
            choice.clinician.pk if choice.clinician else None,
            patient.pk,
            None,
        )
        placed = place_appointment(command, self.user)
        if isinstance(placed, Failure):
            return self._refused(request, placed)
        return admin_redirect(
            appointment_path(placed.value.pk), f"Booked an appointment for {patient.full_name}."
        )

    def _refused(self, request: HttpRequest, failure: Failure) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        times = request.path.removesuffix("/review") + "/times?" + _carried(request)
        return admin_refused_page(request, self.user, failure, (times, TIMES_ACTION_TEXT))


def _carried(request: HttpRequest, **extra: str) -> str:
    """The patient and provider of this step as an address query, plus what a link adds."""
    kept = {name: request.GET[name] for name in ("patient", "provider") if name in request.GET}
    return urlencode({**kept, **extra})


def admin_book_routes() -> list[URLPattern]:
    base = "admin-console/appointments/new"
    return [
        path(base, PatientStepPage.as_view()),
        path(f"{base}/service", ServiceStepPage.as_view()),
        path(f"{base}/<uuid:appointment_type_id>/provider", ProviderStepPage.as_view()),
        path(f"{base}/<uuid:appointment_type_id>/times", TimesStepPage.as_view()),
        path(f"{base}/<uuid:appointment_type_id>/review", ReviewStepPage.as_view()),
    ]
