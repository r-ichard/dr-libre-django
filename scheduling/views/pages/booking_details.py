"""Task 12a, details and review: the visitor's form that creates the hold, and the signed-in
patient's one-page review that books."""

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.booking_refusals import refusal_for
from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.vocabulary import Role
from scheduling.models import User
from scheduling.use_cases.booking_holds import create_hold
from scheduling.use_cases.booking_page_data import SlotChoice, slot_choice
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.views.network_address import network_address
from scheduling.views.pages.booking_forms import (
    DetailsForm,
    hold_command_from,
    read_details,
    reason_error,
)
from scheduling.views.pages.booking_links import (
    SlotRequest,
    code_href,
    confirmation_href,
    instant_from,
    path_uuid,
    provider_from,
)
from scheduling.views.pages.booking_refusal import WayBack, refused_page
from scheduling.views.pages.booking_summary import slot_summary
from scheduling.views.pages.page_view import PageView, render_page

NOTICE_WAYS = ("retry", "wait")


class DetailsPage(PageView):
    template_name = "booking/details.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        refused = self._refuse_staff(request)
        if refused is not None:
            return refused
        slot, choice = self._slot(request)
        if self.user is None:
            return self._details(request, slot, choice, DetailsForm())
        return self._review(request, slot, choice, "", "")

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        refused = self._refuse_staff(request)
        if refused is not None:
            return refused
        slot, choice = self._slot(request)
        if self.user is None:
            return self._create_hold(request, slot, choice)
        return self._book(request, slot, choice, self.user)

    def _refuse_staff(self, request: HttpRequest) -> HttpResponse | None:
        if self.user is None or Role(self.user.role) == Role.PATIENT:
            return None
        return render_page(request, "errors/403.html", status=403, signed_in_user=self.user)

    def _slot(self, request: HttpRequest) -> tuple[SlotRequest, SlotChoice]:
        type_id = path_uuid(self, "appointment_type_id")
        provider_id = provider_from(request.GET.get("provider", ""))
        starts_at = instant_from(request.GET.get("starts_at", ""))
        choice = slot_choice(type_id, provider_id)
        if starts_at is None or choice is None:
            raise Http404
        return SlotRequest(type_id, provider_id, starts_at), choice

    def _create_hold(
        self, request: HttpRequest, slot: SlotRequest, choice: SlotChoice
    ) -> HttpResponse:
        form = read_details(request.POST)
        if form.field_errors:
            return self._details(request, slot, choice, form, 422)
        created = create_hold(hold_command_from(form, slot), network_address(request))
        if isinstance(created, Failure):
            return self._hold_refused(request, slot, choice, form, created)
        return HttpResponseRedirect(code_href(created.value.pk), status=303)

    def _hold_refused(
        self,
        request: HttpRequest,
        slot: SlotRequest,
        choice: SlotChoice,
        form: DetailsForm,
        failure: Failure,
    ) -> HttpResponse:
        if failure.code == FailureCode.INVALID_INPUT:
            form.add_failure(failure)
            return self._details(request, slot, choice, form, 422)
        refusal = refusal_for(failure)
        if refusal.way_forward in NOTICE_WAYS:
            return self._details(request, slot, choice, form, refusal.status, refusal.message)
        return refused_page(request, failure, WayBack(slot.type_id, slot.provider_id), self.user)

    def _book(
        self, request: HttpRequest, slot: SlotRequest, choice: SlotChoice, patient: User
    ) -> HttpResponse:
        error = reason_error(request.POST)
        reason = request.POST.get("reason", "").strip()
        if error:
            return self._review(request, slot, choice, reason, error, 422)
        command = PlacementCommand(
            slot.type_id, slot.starts_at, slot.provider_id, None, None, reason=reason
        )
        placed = place_appointment(command, patient)
        if isinstance(placed, Failure):
            way_back = WayBack(slot.type_id, slot.provider_id, request.get_full_path())
            return refused_page(request, placed, way_back, patient)
        return HttpResponseRedirect(confirmation_href(placed.value.pk), status=303)

    def _details(
        self,
        request: HttpRequest,
        slot: SlotRequest,
        choice: SlotChoice,
        form: DetailsForm,
        status: int = 200,
        notice: str = "",
    ) -> HttpResponse:
        context = {
            "summary": slot_summary(choice, slot.starts_at),
            "form": form,
            "action": request.get_full_path(),
            "notice": notice,
        }
        return self.page(request, context, status)

    def _review(
        self,
        request: HttpRequest,
        slot: SlotRequest,
        choice: SlotChoice,
        reason: str,
        error: str,
        status: int = 200,
    ) -> HttpResponse:
        context = {
            "summary": slot_summary(choice, slot.starts_at),
            "reason": reason,
            "error": error,
            "review_errors": [{"target": "id_reason", "message": error}],
            "action": request.get_full_path(),
        }
        return render_page(
            request, "booking/review.html", context, status=status, signed_in_user=self.user
        )
