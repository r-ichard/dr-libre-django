"""Task 15: the patient's waitlist: join form, own entries and accepting an offer. The patient
comes from the session; the record rule answers 404 for a missing entry and 403 for another's."""

from zoneinfo import ZoneInfo

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.vocabulary import Role
from scheduling.domain.waitlist_window import window_instants
from scheduling.models import AppointmentType, User
from scheduling.use_cases.schedule_loading import active_appointment_type
from scheduling.use_cases.waitlist import JoinCommand, accept_offer, join_waitlist
from scheduling.use_cases.waitlist_inbox import (
    joinable_providers,
    joinable_types,
    own_entry,
    own_waitlist,
)
from scheduling.views.pages.booking_links import path_uuid
from scheduling.views.pages.page_view import PageView, render_page
from scheduling.views.pages.patient_refusal import waitlist_refused_page
from scheduling.views.pages.patient_rows import LIST_PATH
from scheduling.views.pages.patient_waitlist_rows import WAITLIST_PATH, waitlist_row
from scheduling.views.pages.portal_forms import (
    day_or_none,
    failure_messages,
    summary_items,
    uuid_or_none,
)

NOTICES = {"joined": "You are on the waitlist."}
CHOOSE_TYPE = "Choose a service."
WRONG_PROVIDER = "That provider does not offer this service."
REAL_DATE = "Enter a real date, for example 2030-03-27."
FORM_FIELDS = ("appointment_type", "provider", "earliest_day", "latest_day")
USE_CASE_FIELDS = {"latest_at": "latest_day", "earliest_at": "earliest_day"}


class WaitlistPage(PageView):
    template_name = "patient/waitlist.html"
    allowed_roles = frozenset({Role.PATIENT})

    def get(self, request: HttpRequest) -> HttpResponse:
        return self._render(request, {}, {})

    def post(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        entered = {name: request.POST.get(name, "").strip() for name in FORM_FIELDS}
        errors = _join_errors(entered, self.user)
        if errors:
            return self._render(request, entered, errors, 422)
        return HttpResponseRedirect(f"{WAITLIST_PATH}?notice=joined", status=303)

    def _render(
        self,
        request: HttpRequest,
        entered: dict[str, str],
        errors: dict[str, str],
        status: int = 200,
    ) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        types = joinable_types()
        context = {
            "notice": NOTICES.get(request.GET.get("notice", ""), ""),
            "entries": [waitlist_row(entry) for entry in own_waitlist(self.user)],
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
        }
        return self.page(request, context, status)


class AcceptOfferPage(PageView):
    allowed_roles = frozenset({Role.PATIENT})

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        entry_id = path_uuid(self, "entry_id")
        found = own_entry(entry_id, self.user)
        if isinstance(found, Failure):
            if found.code == FailureCode.NOT_FOUND:
                raise Http404
            return render_page(request, "errors/403.html", status=403, signed_in_user=self.user)
        accepted = accept_offer(entry_id, self.user)
        if isinstance(accepted, Failure):
            return waitlist_refused_page(request, accepted, self.user)
        return HttpResponseRedirect(f"{LIST_PATH}?notice=booked", status=303)


def _type_label(appointment_type: AppointmentType) -> str:
    department = appointment_type.department
    return f"{appointment_type.name}, {department.name}, {department.hospital.name}"


def _join_errors(entered: dict[str, str], user: User) -> dict[str, str]:
    """Empty when the entry was joined; otherwise field name to message."""
    errors: dict[str, str] = {}
    type_id = uuid_or_none(entered["appointment_type"])
    appointment_type = active_appointment_type(type_id) if type_id else None
    if appointment_type is None:
        errors["appointment_type"] = CHOOSE_TYPE
    provider_id = uuid_or_none(entered["provider"])
    if entered["provider"] and provider_id is None:
        errors["provider"] = WRONG_PROVIDER
    first, last = day_or_none(entered["earliest_day"]), day_or_none(entered["latest_day"])
    if first is None:
        errors["earliest_day"] = REAL_DATE
    if last is None:
        errors["latest_day"] = REAL_DATE
    if errors or appointment_type is None or first is None or last is None:
        return errors
    zone = ZoneInfo(appointment_type.department.hospital.time_zone)
    window = window_instants(first, last, zone)
    if isinstance(window, Failure):
        return failure_messages(window)
    command = JoinCommand(appointment_type.pk, window.value[0], window.value[1], provider_id, None)
    joined = join_waitlist(command, user)
    if isinstance(joined, Failure):
        return _use_case_errors(joined, bool(provider_id))
    return {}


def _use_case_errors(failure: Failure, provider_named: bool) -> dict[str, str]:
    if failure.code == FailureCode.INVALID_INPUT:
        return {
            USE_CASE_FIELDS.get(name, name): text
            for name, text in failure_messages(failure).items()
        }
    if provider_named:
        return {"provider": WRONG_PROVIDER}
    return {"appointment_type": CHOOSE_TYPE}
