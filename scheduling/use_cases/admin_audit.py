"""Section 10: the read-only audit list for admins. The log only grows, so a deep page must not
read the rows it skips: the page is cut from an index walk of primary keys, then fetched whole."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.search_ordering import Page, page_bounds
from scheduling.models import AuditLogEntry

PAGE_SIZE = 20
NEWEST_FIRST = ("-created_at", "-id")


@dataclass(frozen=True)
class AuditFilters:
    actor_id: UUID | None = None
    entity_type: str = ""
    starts_from: datetime | None = None
    starts_before: datetime | None = None


def list_audit(filters: AuditFilters, page: int) -> Page[AuditLogEntry]:
    matching = AuditLogEntry.objects.all()
    if filters.actor_id is not None:
        matching = matching.filter(actor_id=filters.actor_id)
    if filters.entity_type:
        matching = matching.filter(entity_type=filters.entity_type)
    if filters.starts_from is not None:
        matching = matching.filter(created_at__gte=filters.starts_from)
    if filters.starts_before is not None:
        matching = matching.filter(created_at__lt=filters.starts_before)
    total = matching.count()
    bounds = page_bounds(total, page, PAGE_SIZE)
    wanted = matching.order_by(*NEWEST_FIRST).values("pk")[bounds.first : bounds.first + PAGE_SIZE]
    rows = (
        AuditLogEntry.objects.filter(pk__in=wanted)
        .select_related("actor")
        .only(
            "created_at",
            "action",
            "entity_type",
            "entity_id",
            "correlation_id",
            "actor",
            "actor__full_name",
        )
        .order_by(*NEWEST_FIRST)
    )
    return Page(list(rows), total, bounds.page, bounds.page_count)
