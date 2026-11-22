"""Section 10: the audit log as a read-only admin list. A GET form filters it; nothing here can
write, and the route answers 405 to every other method."""

from datetime import UTC, datetime, time, timedelta

from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, path
from django.views.decorators.csrf import csrf_exempt

from scheduling.domain.audit_entity_types import AUDITED_ENTITY_TYPES
from scheduling.domain.audit_labels import audit_label
from scheduling.domain.vocabulary import Role
from scheduling.models import AuditLogEntry, User
from scheduling.use_cases.admin_audit import AuditFilters, list_audit
from scheduling.views.pages.admin_filters import (
    DayRange,
    choice_param,
    day_range,
    page_links,
    page_number,
    uuid_param,
)
from scheduling.views.pages.page_view import PageView

AUDIT_PATH = "/admin-console/audit"
STAFF_LIMIT = 200


class AuditPage(PageView):
    template_name = "admin/audit.html"
    allowed_roles = frozenset({Role.ADMIN})
    http_method_names = ["get"]

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        actor_id = uuid_param(request, "actor")
        entity_type = choice_param(request, "entity_type", AUDITED_ENTITY_TYPES)
        days = day_range(request)
        found = list_audit(
            AuditFilters(actor_id, entity_type, *_instants(days)), page_number(request)
        )
        asked = {
            "actor": str(actor_id or ""),
            "entity_type": entity_type,
            "from": days.first.isoformat() if days.first else "",
            "to": days.last.isoformat() if days.last else "",
        }
        word = "entry" if found.total == 1 else "entries"
        context = {
            "rows": [_row(entry) for entry in found.items],
            "total_text": f"{found.total} {word}",
            "asked": asked,
            "actors": [("", "Anyone")] + _staff_options(),
            "entity_types": [("", "Any record")]
            + [(name, name) for name in sorted(AUDITED_ENTITY_TYPES)],
            "base_path": AUDIT_PATH,
            "current": "audit",
            "page": found.page,
            "page_count": found.page_count,
            **page_links(AUDIT_PATH, asked, found.page, found.page_count),
        }
        return self.page(request, context)


def _instants(days: DayRange) -> tuple[datetime | None, datetime | None]:
    first = datetime.combine(days.first, time.min, UTC) if days.first else None
    before = datetime.combine(days.last + timedelta(days=1), time.min, UTC) if days.last else None
    return first, before


def _staff_options() -> list[tuple[str, str]]:
    staff = User.objects.exclude(role=Role.PATIENT).order_by("full_name", "pk")[:STAFF_LIMIT]
    return [(str(user.pk), f"{user.full_name} ({user.role.lower()})") for user in staff]


def _row(entry: AuditLogEntry) -> dict[str, str]:
    return {
        "time": f"{entry.created_at.astimezone(UTC):%Y-%m-%d %H:%M:%S} UTC",
        "actor": entry.actor.full_name if entry.actor else "System",
        "action": f"{audit_label(entry.action)} ({entry.action})",
        "entity": f"{entry.entity_type} {entry.entity_id}",
        "correlation_id": entry.correlation_id,
    }


def admin_audit_routes() -> list[URLPattern]:
    # Exempt so a write method meets the 405, not a token check: the view reads and nothing else.
    return [path("admin-console/audit", csrf_exempt(AuditPage.as_view()))]
