"""The patient's notification list and marking as read. Both writes are use cases that
touch only the patient's own rows; the record rule answers 404 or 403 for a foreign id."""

from math import ceil
from zoneinfo import ZoneInfo

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.vocabulary import Role
from scheduling.models import Notification
from scheduling.use_cases.notification_inbox import (
    mark_all_read,
    mark_read,
    notifications_page,
    unread_count,
)
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.booking_links import path_uuid
from scheduling.views.pages.page_view import PageView, render_page
from scheduling.views.pages.patient_appointments import PAGE_SIZE, page_number

PATH = "/patient/notifications"


class NotificationsPage(PageView):
    template_name = "patient/notifications.html"
    allowed_roles = frozenset({Role.PATIENT})

    def get(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        page = page_number(request.GET.get("page", ""))
        found = notifications_page(self.user, page, PAGE_SIZE)
        page_count = max(1, ceil(found.total / PAGE_SIZE))
        context = {
            "rows": [{"item": row, "shown_at": _shown_at(row)} for row in found.rows],
            "unread": unread_count(self.user),
            "page": page,
            "page_count": page_count,
            "previous_href": f"{PATH}?page={page - 1}" if page > 1 else "",
            "next_href": f"{PATH}?page={page + 1}" if page < page_count else "",
            "return_to": f"{PATH}?page={page}",
            "now": current_request_context().now,
        }
        return self.page(request, context)


def _shown_at(row: Notification) -> str:
    """The time in the zone of the hospital the notice is about, named; UTC when it has none."""
    linked = row.appointment or row.waitlist_entry
    zone_name = linked.appointment_type.department.hospital.time_zone if linked else "UTC"
    local = row.created_at.astimezone(ZoneInfo(zone_name))
    return f"{local.day} {local:%B %Y, %H:%M} ({zone_name})"


class MarkReadPage(PageView):
    form_page = PATH
    allowed_roles = frozenset({Role.PATIENT})

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        marked = mark_read(path_uuid(self, "notification_id"), self.user)
        if isinstance(marked, Failure):
            if marked.code == FailureCode.NOT_FOUND:
                raise Http404
            return render_page(request, "errors/403.html", status=403, signed_in_user=self.user)
        return _back_to_list(request)


class MarkAllReadPage(PageView):
    form_page = PATH
    allowed_roles = frozenset({Role.PATIENT})

    def post(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        mark_all_read(self.user)
        return _back_to_list(request)


def _back_to_list(request: HttpRequest) -> HttpResponse:
    page = page_number(request.POST.get("page", ""))
    return HttpResponseRedirect(f"{PATH}?page={page}", status=303)
