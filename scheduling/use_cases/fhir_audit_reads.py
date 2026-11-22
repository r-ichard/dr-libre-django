"""Task 24, spec 4, 15.4: read and search `AuditEvent`, for an admin only. The log only grows, so
a search is one counted, ordered page of keys and the rows are loaded after."""

from functools import reduce
from operator import or_
from uuid import UUID

from django.db.models import Model, Q, QuerySet

from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.fhir_audit_action import EXPLICIT_CODES, SUFFIX_CODES, product_actions_of
from scheduling.domain.fhir_audit_event import AuditFacts, audit_event_resource
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_search import SearchQuery
from scheduling.domain.vocabulary import Role
from scheduling.models import AuditLogEntry
from scheduling.use_cases.fhir_appointment_reads import starts_within
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_reads import Part, SearchPage, search_part


def read_audit_event(identifier: str, caller: Caller) -> Result[Resource]:
    refusal = _refusal(caller)
    if refusal is not None:
        return refusal
    if not AuditLogEntry.objects.filter(pk=identifier).exists():
        return Failure.not_found()
    return Success(_events([UUID(identifier)])[0])


def search_audit_events(query: SearchQuery, caller: Caller) -> Result[SearchPage]:
    refusal = _refusal(caller)
    return refusal if refusal is not None else Success(search_part(AUDIT_EVENTS, query))


def _refusal(caller: Caller) -> Failure | None:
    if caller.user is None:
        return Failure.unauthenticated()
    return None if caller.role is Role.ADMIN else Failure.forbidden()


def _entity(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    entity_type, separator, entity_id = value.rpartition("/")
    if separator:
        return rows.filter(entity_type__iexact=entity_type, entity_id=entity_id)
    return rows.filter(entity_id=value)


def _agent(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    return rows.filter(actor_id=value)


def _entity_type(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    return rows.filter(entity_type__iexact=value)


def _action(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    """`action=C` finds the events whose resource shows `C`, whatever the product action is."""
    shown = product_actions_of(value)
    by_suffix = reduce(or_, (Q(action__endswith=item) for item in SUFFIX_CODES), Q(pk__in=[]))
    if shown.is_remainder:
        return rows.exclude(Q(action__in=EXPLICIT_CODES) | by_suffix)
    own_suffix = reduce(or_, (Q(action__endswith=item) for item in shown.suffixes), Q(pk__in=[]))
    return rows.filter(
        Q(action__in=shown.named) | (own_suffix & ~Q(action__in=shown.claimed_elsewhere))
    )


def _product_action(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    """`type` is where the resource shows the product's own action name."""
    return rows.filter(action=value)


def _events(identifiers: list[UUID]) -> list[Resource]:
    rows = AuditLogEntry.objects.filter(pk__in=identifiers).select_related("actor").order_by("pk")
    return [
        audit_event_resource(
            AuditFacts(
                row.pk,
                row.version,
                row.updated_at,
                row.created_at,
                row.action,
                None if row.actor is None else _actor_type(row.actor.role),
                row.actor_id,
                row.entity_type,
                row.entity_id,
                row.metadata,
                row.correlation_id,
            )
        )
        for row in rows
    ]


def _actor_type(role: str) -> str:
    return "Patient" if role == Role.PATIENT else "Practitioner"


AUDIT_EVENTS = Part(
    visible=lambda: AuditLogEntry.objects.all(),
    everything=lambda: AuditLogEntry.objects.all(),
    id_column="pk",
    sort_columns={},
    newest_column="created_at",
    filters={
        "agent": _agent,
        "entity": _entity,
        "entity-type": _entity_type,
        "action": _action,
        "type": _product_action,
        "date": starts_within("created_at"),
    },
    build=_events,
)
