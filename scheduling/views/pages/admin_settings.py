"""Section 10: the booking policy as the rules read it (read only) and the reminder button."""

from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, path

from scheduling.domain import booking_rules
from scheduling.domain.vocabulary import Role
from scheduling.use_cases.reminders import send_reminders
from scheduling.views.pages.admin_notices import admin_redirect
from scheduling.views.pages.page_view import PageView

SETTINGS_PATH = "/admin-console/settings"
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
MAXIMUM_REMINDER_DIGITS = 6


class SettingsPage(PageView):
    template_name = "admin/settings.html"
    allowed_roles = frozenset({Role.ADMIN})
    http_method_names = ["get"]

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        lead_minutes = int(booking_rules.LEAD_TIME.total_seconds() // SECONDS_PER_MINUTE)
        cancellation_hours = int(
            booking_rules.CANCELLATION_WINDOW.total_seconds() // SECONDS_PER_HOUR
        )
        context = {
            "lead_minutes": lead_minutes,
            "cancellation_hours": cancellation_hours,
            "open_bookings": booking_rules.OPEN_ONLINE_BOOKINGS_MAXIMUM,
            "action": f"{SETTINGS_PATH}/reminders",
            "current": "settings",
        }
        return self.page(request, context)


class RemindersPage(PageView):
    allowed_roles = frozenset({Role.ADMIN})
    http_method_names = ["post"]

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        created = send_reminders(self.user)
        return admin_redirect(SETTINGS_PATH, f"reminders:{created}")


def admin_settings_routes() -> list[URLPattern]:
    return [
        path("admin-console/settings", SettingsPage.as_view()),
        path("admin-console/settings/reminders", RemindersPage.as_view()),
    ]
