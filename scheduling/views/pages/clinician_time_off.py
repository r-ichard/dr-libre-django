"""Task 17, time off: list, record, delete. Recording never cancels an appointment, and the page
says so. A period typed into the check form lists the appointments inside it before anything is
recorded: two plain forms, no script."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.request_limits import day_in_range
from scheduling.models import Appointment, ClinicianProfile, TimeOff
from scheduling.use_cases.clinician_availability import appointments_in, own_time_off
from scheduling.use_cases.time_off import TimeOffCommand, create_time_off, delete_time_off
from scheduling.views.pages.booking_links import path_uuid
from scheduling.views.pages.clinician_support import (
    TIME_OFF_PATH,
    ClinicianPage,
    appointment_path,
)
from scheduling.views.pages.local_time import errors_by_field, utc_from_local

NOT_A_TIME = (
    "Enter a date and time that exists in the hospital's time zone; clocks skip one hour in spring."
)
NOT_A_DATE = "That date does not exist"
FORM_FIELDS = ("starts_at", "ends_at", "reason")


def _unreadable_message(raw: str) -> str:
    """A date that never exists is named as such; only a real date skipped by a clock change
    gets the sentence about the clock."""
    if not raw:
        return NOT_A_TIME
    try:
        day = date.fromisoformat(raw[:10])
    except ValueError:
        return NOT_A_DATE
    return NOT_A_TIME if day_in_range(day) else NOT_A_DATE


def _stamp(moment: datetime, zone: ZoneInfo) -> str:
    return f"{moment.astimezone(zone):%d %b %Y, %H:%M %Z}"


def _period_of(values: dict[str, str], zone: ZoneInfo) -> tuple[datetime, datetime] | None:
    starts_at = utc_from_local(values["starts_at"], zone)
    ends_at = utc_from_local(values["ends_at"], zone)
    if starts_at is None or ends_at is None or ends_at <= starts_at:
        return None
    return starts_at, ends_at


class TimeOffPage(ClinicianPage):
    template_name = "clinician/time_off.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        values = {name: request.GET.get(name, "") for name in FORM_FIELDS}
        errors: dict[str, str] = {}
        preview: list[Appointment] | None = None
        if values["starts_at"] or values["ends_at"]:
            period = _period_of(values, _zone_of(profile))
            if period is None:
                errors = {"ends_at": "Enter a start and an end after it, in the hospital's zone."}
            else:
                preview = appointments_in(profile, *period)
        return self._render(request, profile, values, errors, preview)

    def post(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        values = {name: request.POST.get(name, "") for name in FORM_FIELDS}
        zone = _zone_of(profile)
        starts_at = utc_from_local(values["starts_at"], zone)
        ends_at = utc_from_local(values["ends_at"], zone)
        errors = {
            name: _unreadable_message(values[name])
            for name, moment in (("starts_at", starts_at), ("ends_at", ends_at))
            if moment is None
        }
        if starts_at is None or ends_at is None:
            return self._render(request, profile, values, errors, None, 422)
        created = create_time_off(TimeOffCommand(starts_at, ends_at, values["reason"]), self.user)
        if isinstance(created, Failure):
            if created.code != FailureCode.INVALID_INPUT:
                return self.refusal_of(request, created)
            return self._render(request, profile, values, errors_by_field(created), None, 422)
        return HttpResponseRedirect(TIME_OFF_PATH, status=303)

    def _render(
        self,
        request: HttpRequest,
        profile: ClinicianProfile,
        values: dict[str, str],
        errors: dict[str, str],
        preview: list[Appointment] | None,
        status: int = 200,
    ) -> HttpResponse:
        zone = _zone_of(profile)
        context = {
            "time_zone": profile.department.hospital.time_zone,
            "rows": [_row_of(row, zone) for row in own_time_off(profile)],
            "values": values,
            "errors": errors,
            "summary": [
                {"target": f"id_{name}", "message": message} for name, message in errors.items()
            ],
            "preview": None if preview is None else [_visit_of(row, zone) for row in preview],
            "action": TIME_OFF_PATH,
        }
        return self.page(request, context, status)


def _zone_of(profile: ClinicianProfile) -> ZoneInfo:
    return ZoneInfo(profile.department.hospital.time_zone)


def _row_of(row: TimeOff, zone: ZoneInfo) -> dict[str, str]:
    return {
        "id": str(row.pk),
        "starts": _stamp(row.starts_at, zone),
        "ends": _stamp(row.ends_at, zone),
        "reason": row.reason,
        "delete_href": f"{TIME_OFF_PATH}/{row.pk}/delete",
    }


def _visit_of(row: Appointment, zone: ZoneInfo) -> dict[str, str]:
    return {
        "when": _stamp(row.starts_at, zone),
        "text": f"{row.appointment_type.name}, {row.patient.full_name}",
        "href": appointment_path(row.pk),
    }


class TimeOffDeletePage(ClinicianPage):
    template_name = "clinician/time_off_delete.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        row = TimeOff.objects.filter(pk=path_uuid(self, "time_off_id")).first()
        if row is None:
            return self.refusal_of(request, Failure.not_found())
        if row.clinician_id != profile.pk:
            return self.refusal_of(request, Failure.forbidden())
        context = {"row": _row_of(row, _zone_of(profile)), "action": request.path}
        return self.page(request, {**context, "back_path": TIME_OFF_PATH})

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        deleted = delete_time_off(path_uuid(self, "time_off_id"), self.user)
        if isinstance(deleted, Failure):
            return self.refusal_of(request, deleted)
        return HttpResponseRedirect(TIME_OFF_PATH, status=303)
