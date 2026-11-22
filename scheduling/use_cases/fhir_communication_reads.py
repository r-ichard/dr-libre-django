"""Task 24, spec 15.4: read, search and update `Communication`. The recipient reads the own
notifications and nobody else's, an admin included. An update only marks as read, through the
use case of task 15."""

from uuid import UUID

from django.db.models import Model, QuerySet

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_communication import (
    CommunicationFacts,
    NoChange,
    communication_resource,
    decode_update,
)
from scheduling.domain.fhir_search import SearchQuery
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.domain.vocabulary import Role
from scheduling.models import Notification, User
from scheduling.use_cases.fhir_appointment_reads import starts_within
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_reads import Part, SearchPage, search_part
from scheduling.use_cases.notification_inbox import mark_read

REFUSED_MESSAGE = "This element cannot be changed."


def read_communication(identifier: str, caller: Caller) -> Result[Resource]:
    if caller.user is None:
        return Failure.unauthenticated()
    part = _part(caller.user)
    if part.visible().filter(pk=identifier).exists():
        return Success(part.build([UUID(identifier)])[0])
    return Failure.forbidden()


def search_communications(query: SearchQuery, caller: Caller) -> Result[SearchPage]:
    if caller.user is None:
        return Failure.unauthenticated()
    return Success(search_part(_part(caller.user), query))


def update_communication(
    identifier: UUID, body: dict[str, object], caller: Caller, expected_version: int | None
) -> Result[Resource]:
    user = caller.user
    stored = read_communication(str(identifier), caller)
    if isinstance(stored, Failure) or user is None:
        return stored if isinstance(stored, Failure) else Failure.unauthenticated()
    if expected_version is not None and expected_version != _stored_version(stored.value):
        return stale_version()
    command = decode_update(stored.value, body)
    if isinstance(command, str):
        return Failure.invalid_input([FieldMessage(command, REFUSED_MESSAGE)])
    if isinstance(command, NoChange):
        return stored
    marked = mark_read(identifier, user)
    if isinstance(marked, Failure):
        return marked
    return Success(_communications([identifier])[0])


def _stored_version(resource: Resource) -> int:
    meta_block = resource["meta"]
    return int(str(meta_block["versionId"])) if isinstance(meta_block, dict) else 0


def _part(user: User) -> Part:
    def rows() -> QuerySet[Model]:
        return Notification.objects.filter(recipient=user)

    return Part(
        visible=rows,
        everything=rows,
        id_column="pk",
        sort_columns={"sent": "created_at"},
        filters={
            "recipient": lambda found, value: found.filter(recipient_id=value),
            "category": _kind,
            "sent": starts_within("created_at"),
        },
        build=_communications,
    )


def _kind(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    return rows.filter(kind__iexact=value)


def _communications(identifiers: list[UUID]) -> list[Resource]:
    rows = (
        Notification.objects.filter(pk__in=identifiers)
        .select_related("recipient", "appointment")
        .order_by("pk")
    )
    return [communication_resource(_facts(row)) for row in rows]


def _facts(row: Notification) -> CommunicationFacts:
    appointment = row.appointment
    about = row.waitlist_entry_id
    if appointment is not None:
        about = appointment.waitlist_entry_id or appointment.pk
    return CommunicationFacts(
        row.pk,
        row.version,
        row.updated_at,
        row.kind,
        "Patient" if row.recipient.role == Role.PATIENT else "Practitioner",
        row.recipient_id,
        row.title,
        row.body,
        row.created_at,
        row.read_at,
        about,
    )
