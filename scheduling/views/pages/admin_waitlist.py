"""Section 10: the admin's waitlist: the list, adding a patient, a manual offer, accepting an
offer for the patient. Every write is a use case of task 09; these pages parse and format."""

from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, path

from scheduling.domain.failure import Failure
from scheduling.domain.vocabulary import Role, WaitlistStatus
from scheduling.models import AppointmentType, WaitlistEntry
from scheduling.use_cases.admin_waitlist import active_patient, list_waitlist, search_patients
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.schedule_loading import active_appointment_type
from scheduling.use_cases.waitlist import (
    JoinCommand,
    accept_offer,
    clinician_offers_type,
    join_waitlist,
    offer_waitlist_entry,
    window_failure,
)
from scheduling.use_cases.waitlist_inbox import joinable_providers, joinable_types
from scheduling.views.pages.admin_filters import (
    choice_param,
    page_links,
    page_number,
    patient_links,
    search_text,
)
from scheduling.views.pages.admin_notices import admin_redirect
from scheduling.views.pages.admin_refusal import admin_refused_page
from scheduling.views.pages.booking_links import path_uuid
from scheduling.views.pages.local_time import utc_from_local
from scheduling.views.pages.page_view import PageView
from scheduling.views.pages.patient_waitlist_rows import waitlist_row
from scheduling.views.pages.portal_forms import failure_messages, summary_items, uuid_or_none

LIST_PATH = "/admin-console/waitlist"
ADD_PATH = f"{LIST_PATH}/new"
STATUSES = {status.value: status.value.capitalize() for status in WaitlistStatus}
CHOOSE_PATIENT = "Choose a patient."
CHOOSE_TYPE = "Choose a service."
WRONG_PROVIDER = "That provider does not offer this service."
REAL_MOMENT = "Enter a date and a time."
BACK_TO_LIST = (LIST_PATH, "Back to the waitlist")
FORM_FIELDS = ("patient", "appointment_type", "preferred_clinician", "earliest_at", "latest_at")


class AdminWaitlistPage(PageView):
    allowed_roles = frozenset({Role.ADMIN})


class WaitlistListPage(AdminWaitlistPage):
    template_name = "admin/waitlist.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        status = choice_param(request, "status", STATUSES)
        found = list_waitlist(status, page_number(request))
        asked = {"status": status}
        word = "entry" if found.total == 1 else "entries"
        context = {
            "rows": [_row(entry) for entry in found.items],
            "total_text": f"{found.total} {word}",
            "status_options": [("", "Any status"), *STATUSES.items()],
            "asked": asked,
            "base_path": LIST_PATH,
            "add_path": ADD_PATH,
            "current": "waitlist",
            "page": found.page,
            "page_count": found.page_count,
            **page_links(LIST_PATH, asked, found.page, found.page_count),
        }
        return self.page(request, context)


def _row(entry: WaitlistEntry) -> dict[str, object]:
    waiting = entry.status == WaitlistStatus.WAITING
    offered = entry.status == WaitlistStatus.OFFERED
    return {
        **waitlist_row(entry),
        "patient": entry.patient.full_name,
        "offer_action": f"{LIST_PATH}/{entry.pk}/offer" if waiting else "",
        "accept_action": f"{LIST_PATH}/{entry.pk}/accept" if offered else "",
    }


class WaitlistAddPage(AdminWaitlistPage):
    template_name = "admin/waitlist_add.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        entered = {"patient": request.GET.get("patient", "")}
        return self._render(request, entered, {}, search_text(request))

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        entered = {name: request.POST.get(name, "").strip() for name in FORM_FIELDS}
        errors, command = _checked(entered)
        if command is None:
            return self._render(request, entered, errors, "", 422)
        joined = join_waitlist(command, self.user)
        if isinstance(joined, Failure):
            return admin_refused_page(request, self.user, joined, BACK_TO_LIST)
        name = joined.value.patient.full_name
        return admin_redirect(LIST_PATH, f"Added {name} to the waitlist.")

    def _render(
        self,
        request: HttpRequest,
        entered: dict[str, str],
        errors: dict[str, str],
        query: str,
        status: int = 200,
    ) -> HttpResponse:
        patient = active_patient(uuid_or_none(entered["patient"]))
        types = joinable_types()
        context = {
            "patient": patient,
            "found": patient_links(search_patients(query), ADD_PATH),
            "query": query,
            "search_action": ADD_PATH,
            "type_options": [("", "Choose a service")]
            + [(str(item.pk), _type_label(item)) for item in types],
            "provider_options": [("", "Any provider")]
            + [
                (str(item.pk), f"{item.title} {item.user.full_name}, {item.specialty.name}")
                for item in joinable_providers(types)
            ],
            "entered": entered,
            "errors": errors,
            "summary": summary_items(errors),
            "action": ADD_PATH,
            "back_path": LIST_PATH,
            "current": "waitlist",
        }
        return self.page(request, context, status)


def _type_label(appointment_type: AppointmentType) -> str:
    department = appointment_type.department
    return f"{appointment_type.name}, {department.name}, {department.hospital.name}"


def _checked(entered: dict[str, str]) -> tuple[dict[str, str], JoinCommand | None]:
    """Every error of the submission at once; the command only when there is none."""
    errors: dict[str, str] = {}
    patient = active_patient(uuid_or_none(entered["patient"]))
    if patient is None:
        errors["q"] = CHOOSE_PATIENT
    type_id = uuid_or_none(entered["appointment_type"])
    appointment_type = active_appointment_type(type_id, online_only=False) if type_id else None
    if appointment_type is None:
        errors["appointment_type"] = CHOOSE_TYPE
    clinician_id = uuid_or_none(entered["preferred_clinician"])
    if entered["preferred_clinician"] and (
        clinician_id is None
        or (
            appointment_type is not None
            and not clinician_offers_type(appointment_type, clinician_id)
        )
    ):
        errors["preferred_clinician"] = WRONG_PROVIDER
    zone = _zone_of(appointment_type)
    moments = {name: utc_from_local(entered[name], zone) for name in ("earliest_at", "latest_at")}
    errors.update({name: REAL_MOMENT for name, moment in moments.items() if moment is None})
    earliest, latest = moments["earliest_at"], moments["latest_at"]
    if earliest is not None and latest is not None:
        problem = window_failure(earliest, latest, current_request_context().now)
        if problem is not None:
            errors.update(failure_messages(problem))
    if errors or patient is None or appointment_type is None or earliest is None or latest is None:
        return errors, None
    return errors, JoinCommand(appointment_type.pk, earliest, latest, clinician_id, patient.pk)


def _zone_of(appointment_type: AppointmentType | None) -> ZoneInfo:
    if appointment_type is None:
        return ZoneInfo("UTC")
    return ZoneInfo(appointment_type.department.hospital.time_zone)


class OfferPage(AdminWaitlistPage):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        offered = offer_waitlist_entry(path_uuid(self, "entry_id"), self.user)
        if isinstance(offered, Failure):
            return admin_refused_page(
                request, self.user, offered, BACK_TO_LIST, waitlist_offer=True
            )
        return admin_redirect(LIST_PATH, f"Offered a time to {offered.value.patient.full_name}.")


class AcceptPage(AdminWaitlistPage):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        accepted = accept_offer(path_uuid(self, "entry_id"), self.user)
        if isinstance(accepted, Failure):
            return admin_refused_page(request, self.user, accepted, BACK_TO_LIST)
        return admin_redirect(
            LIST_PATH, f"Accepted the offer for {accepted.value.patient.full_name}."
        )


def admin_waitlist_routes() -> list[URLPattern]:
    return [
        path("admin-console/waitlist", WaitlistListPage.as_view()),
        path("admin-console/waitlist/new", WaitlistAddPage.as_view()),
        path("admin-console/waitlist/<uuid:entry_id>/offer", OfferPage.as_view()),
        path("admin-console/waitlist/<uuid:entry_id>/accept", AcceptPage.as_view()),
    ]
