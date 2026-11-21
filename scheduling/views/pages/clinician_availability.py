"""Availability pages: plain form posts answering 303; a refused form is shown again with the
error summary. The use case applies the record rule, so another clinician's rule never leaks."""

from datetime import time
from uuid import UUID

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.availability_rules import WEEKDAY_NAMES, weekday_name
from scheduling.domain.failure import Failure, FailureCode
from scheduling.models import AvailabilityRule, ClinicianProfile
from scheduling.use_cases.availability import RuleCommand, create_rule, delete_rule, update_rule
from scheduling.use_cases.clinician_availability import bookable_rooms, own_rules
from scheduling.views.pages.booking_links import path_uuid
from scheduling.views.pages.clinician_support import AVAILABILITY_PATH, ClinicianPage
from scheduling.views.pages.local_time import errors_by_field

DEFAULT_STEP = "15"
NO_ROOM = ""


def _clock(value: time) -> str:
    return f"{value:%H:%M}"


def _row_of(rule: AvailabilityRule) -> dict[str, object]:
    base = f"{AVAILABILITY_PATH}/{rule.pk}"
    return {
        "weekday": weekday_name(rule.weekday),
        "times": f"{_clock(rule.start_time)} to {_clock(rule.end_time)}",
        "step": rule.slot_step_minutes,
        "room": rule.room.name if rule.room else "No fixed room",
        "edit_href": f"{base}/edit",
        "delete_href": f"{base}/delete",
    }


class AvailabilityPage(ClinicianPage):
    template_name = "clinician/availability.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        rows = [_row_of(rule) for rule in own_rules(profile)]
        return self.page(request, {"rows": rows, "new_href": f"{AVAILABILITY_PATH}/new"})


def _form_values(rule: AvailabilityRule | None) -> dict[str, str]:
    if rule is None:
        return {
            "weekday": "1",
            "start_time": "",
            "end_time": "",
            "slot_step_minutes": DEFAULT_STEP,
            "room": NO_ROOM,
        }
    return {
        "weekday": str(rule.weekday),
        "start_time": _clock(rule.start_time),
        "end_time": _clock(rule.end_time),
        "slot_step_minutes": str(rule.slot_step_minutes),
        "room": str(rule.room_id) if rule.room_id else NO_ROOM,
    }


def _time_from(raw: str) -> time | None:
    try:
        return time.fromisoformat(raw.strip())
    except ValueError:
        return None


def _int_from(raw: str) -> int | None:
    try:
        return int(raw.strip())
    except ValueError:
        return None


def _command_from(values: dict[str, str]) -> RuleCommand | dict[str, str]:
    """A command, or the field errors of values no use case could even read."""
    weekday = _int_from(values["weekday"])
    start, end = _time_from(values["start_time"]), _time_from(values["end_time"])
    step = _int_from(values["slot_step_minutes"])
    room = _uuid_from(values["room"])
    problems: dict[str, str] = {}
    if weekday is None:
        problems["weekday"] = "Choose a day of the week."
    if start is None:
        problems["start_time"] = "Enter a start time such as 09:00."
    if end is None:
        problems["end_time"] = "Enter an end time such as 17:00."
    if step is None:
        problems["slot_step_minutes"] = "Enter the slot step in minutes."
    if values["room"] and room is None:
        problems["room"] = "Choose an active room of your department."
    if problems or weekday is None or start is None or end is None or step is None:
        return problems
    return RuleCommand(weekday, start, end, step, room)


def _uuid_from(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except ValueError:
        return None


class RuleFormPage(ClinicianPage):
    """New rule at /new, edit at /<id>/edit; the same form."""

    template_name = "clinician/rule_form.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        rule = self._rule_or_refusal(request, profile)
        if isinstance(rule, HttpResponse):
            return rule
        return self._form(request, profile, _form_values(rule), {})

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        values = {name: request.POST.get(name, "") for name in _form_values(None)}
        command = _command_from(values)
        if isinstance(command, dict):
            return self._form(request, profile, values, command, 422)
        rule_id = self.kwargs.get("rule_id")
        result = (
            create_rule(command, self.user)
            if rule_id is None
            else update_rule(path_uuid(self, "rule_id"), command, self.user)
        )
        if isinstance(result, Failure):
            if result.code != FailureCode.INVALID_INPUT:
                return self.refusal_of(request, result)
            return self._form(request, profile, values, errors_by_field(result), 422)
        return HttpResponseRedirect(AVAILABILITY_PATH, status=303)

    def _rule_or_refusal(
        self, request: HttpRequest, profile: ClinicianProfile
    ) -> AvailabilityRule | None | HttpResponse:
        if "rule_id" not in self.kwargs:
            return None
        return own_rule_or_refusal(self, request, profile)

    def _form(
        self,
        request: HttpRequest,
        profile: ClinicianProfile,
        values: dict[str, str],
        errors: dict[str, str],
        status: int = 200,
    ) -> HttpResponse:
        editing = "rule_id" in self.kwargs
        rooms = [(NO_ROOM, "No fixed room")] + [
            (str(room.pk), room.name) for room in bookable_rooms(profile)
        ]
        context = {
            "title": "Edit availability" if editing else "New availability",
            "weekdays": [(str(number), name) for number, name in enumerate(WEEKDAY_NAMES)],
            "rooms": rooms,
            "values": values,
            "errors": errors,
            "summary": [
                {"target": f"id_{name}", "message": message} for name, message in errors.items()
            ],
            "back_path": AVAILABILITY_PATH,
        }
        return self.page(request, context, status)


def own_rule_or_refusal(
    page: ClinicianPage, request: HttpRequest, profile: ClinicianProfile
) -> AvailabilityRule | HttpResponse:
    rule = (
        AvailabilityRule.objects.select_related("room")
        .filter(pk=path_uuid(page, "rule_id"))
        .first()
    )
    if rule is None:
        return page.refusal_of(request, Failure.not_found())
    if rule.clinician_id != profile.pk:
        return page.refusal_of(request, Failure.forbidden())
    return rule


class RuleDeletePage(ClinicianPage):
    template_name = "clinician/rule_delete.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        rule = own_rule_or_refusal(self, request, profile)
        if isinstance(rule, HttpResponse):
            return rule
        context = {"row": _row_of(rule), "action": request.path, "back_path": AVAILABILITY_PATH}
        return self.page(request, context)

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        deleted = delete_rule(path_uuid(self, "rule_id"), self.user)
        if isinstance(deleted, Failure):
            return self.refusal_of(request, deleted)
        return HttpResponseRedirect(AVAILABILITY_PATH, status=303)
