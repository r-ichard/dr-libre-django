"""Section 13: the admin dashboard, figures of a range of days ending today. The range comes from
the address; a value that is not one of the three falls back to seven days."""

from django.http import HttpRequest, HttpResponse

from scheduling.domain.report_range import DEFAULT_RANGE_DAYS, RANGE_DAYS
from scheduling.domain.vocabulary import Role
from scheduling.use_cases.admin_report import Report, build_report
from scheduling.views.pages.booking_links import day_label
from scheduling.views.pages.page_view import PageView

HOME_PATH = "/admin-console/"
RANGE_LABELS = {"today": "Today", "7": "7 days", "30": "30 days"}
DEFAULT_RANGE = str(DEFAULT_RANGE_DAYS)


class AdminDashboard(PageView):
    template_name = "admin/dashboard.html"
    allowed_roles = frozenset({Role.ADMIN})
    http_method_names = ["get"]

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        asked = request.GET.get("range", "")
        chosen = asked if asked in RANGE_DAYS else DEFAULT_RANGE
        report = build_report(chosen)
        context = {
            "ranges": [
                {"label": label, "href": f"{HOME_PATH}?range={key}", "current": key == chosen}
                for key, label in RANGE_LABELS.items()
            ],
            "range_text": _range_text(report),
            "tiles": _tiles(report),
            "per_day": [
                {"day": day_label(row.day), "count": row.count, "width": row.bar_width}
                for row in report.per_day
            ],
            "busiest": report.busiest,
            "current": "dashboard",
        }
        return self.page(request, context)


def _range_text(report: Report) -> str:
    if report.first_day == report.last_day:
        return day_label(report.last_day)
    return f"{day_label(report.first_day)} to {day_label(report.last_day)}"


def _tiles(report: Report) -> list[tuple[str, str]]:
    return [
        ("Appointments", str(report.appointments)),
        ("Cancellations", str(report.cancellations)),
        ("Utilisation", report.utilisation),
        ("No-show rate", report.no_show_rate),
        ("Online share", report.online_share),
        ("Waitlist size", str(report.waitlist_size)),
    ]
