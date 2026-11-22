"""Section 10: the pages of the user and clinician records that the shared flow does not cover:
the deactivation step, a clinician's read-only week calendar and the type colours it draws."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import URLPattern, path
from django.utils.cache import patch_cache_control

from scheduling.domain.booking_week import next_week_start, previous_week_start
from scheduling.domain.calendar_grid import HOUR_LABELS
from scheduling.domain.failure import Failure, FailureCode
from scheduling.models import AppointmentType, ClinicianProfile
from scheduling.use_cases import admin_record_reads
from scheduling.use_cases.admin_users import deactivate_user
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.admin_record_kinds import KIND_VIEWS
from scheduling.views.pages.admin_records import STALE_TEXT, UNREADABLE_VERSION, RecordPage
from scheduling.views.pages.booking_links import day_label, path_uuid, week_from
from scheduling.views.pages.clinician_calendar import (
    COLOUR_CACHE_SECONDS,
    COLOUR_PATTERN,
    DAYS_PER_WEEK,
    week_columns,
)
from scheduling.views.pages.time_grid import axis_rows


class DeactivatePage(RecordPage):
    template_name = "admin/deactivate.html"
    kind = "user"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        return self._confirmation(request, [], "")

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        version = request.POST.get("version", "")
        if not (version.isascii() and version.isdigit()):
            return self._confirmation(request, [], UNREADABLE_VERSION, 422)
        result = deactivate_user(path_uuid(self, "record_id"), int(version), self.user)
        if not isinstance(result, Failure):
            return HttpResponseRedirect(f"{self.view.base_path}/{result.value}", status=303)
        if result.code == FailureCode.RULE_VIOLATION:
            reasons = result.details["violated_rules"]
            return self._confirmation(
                request, reasons if isinstance(reasons, list) else [], "", 409
            )
        if result.code == FailureCode.CONFLICT:
            return self._confirmation(request, [], STALE_TEXT, 409)
        return self.refusal_of(request, result)

    def _confirmation(
        self, request: HttpRequest, reasons: list[str], problem: str, status: int = 200
    ) -> HttpResponse:
        record = self.record_or_404()
        upcoming = admin_record_reads.upcoming_for_user(record.pk, current_request_context().now)
        noun = "appointment" if upcoming == 1 else "appointments"
        context = {
            "view": self.view,
            "title": str(getattr(record, "full_name", "")),
            "reasons": reasons,
            "problem": problem,
            "version": record.version,
            "appointments_text": f"This person has {upcoming} upcoming {noun}. They stay booked.",
            "action": request.path,
            "back_path": f"{self.view.base_path}/{record.pk}",
            "current": self.view.path_name,
        }
        return self.page(request, context, status)


class ClinicianCalendarPage(RecordPage):
    template_name = "admin/calendar.html"
    kind = "clinician"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        profile = (
            ClinicianProfile.objects.select_related("user", "department__hospital")
            .filter(pk=path_uuid(self, "record_id"))
            .first()
        )
        if profile is None:
            raise Http404
        time_zone = profile.department.hospital.time_zone
        today = current_request_context().now.astimezone(ZoneInfo(time_zone)).date()
        asked = week_from(request.GET.get("week", "")) or today
        monday = asked - timedelta(days=asked.weekday())
        last_day = monday + timedelta(days=DAYS_PER_WEEK - 1)
        base = f"{self.view.base_path}/{profile.pk}"
        context = {
            "title": profile.user.full_name,
            "columns": week_columns(profile, monday, linked=False),
            "axis": axis_rows(),
            "axis_end": HOUR_LABELS[-1],
            "week_label": f"{day_label(monday)} to {day_label(last_day)}",
            "previous_href": f"{base}/calendar?week={previous_week_start(monday).isoformat()}",
            "next_href": f"{base}/calendar?week={next_week_start(monday).isoformat()}",
            "back_path": base,
            "time_zone": time_zone,
            "current": self.view.path_name,
        }
        return self.page(request, context)


class AdminColoursPage(RecordPage):
    """Every type's colour as a CSS rule: inline style is forbidden, a same-origin sheet is not."""

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        rules = [
            f".type-colour--{row.pk.hex} {{ --type-colour: {row.colour}; }}"
            for row in AppointmentType.objects.all()
            if COLOUR_PATTERN.fullmatch(row.colour)
        ]
        response = HttpResponse("\n".join(rules) + "\n", content_type="text/css")
        patch_cache_control(response, private=True, max_age=COLOUR_CACHE_SECONDS)
        return response


def admin_user_routes() -> list[URLPattern]:
    users = KIND_VIEWS["user"].base_path.removeprefix("/")
    clinicians = KIND_VIEWS["clinician"].base_path.removeprefix("/")
    return [
        path(f"{users}/<uuid:record_id>/deactivate", DeactivatePage.as_view()),
        path(f"{clinicians}/<uuid:record_id>/calendar", ClinicianCalendarPage.as_view()),
        path("admin-console/type-colours.css", AdminColoursPage.as_view()),
    ]
