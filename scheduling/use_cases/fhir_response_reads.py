"""Task 24, spec 15.4: read, search and create `AppointmentResponse`. One exists per booked
waitlist entry; a patient sees the own, an admin all. Creating one runs `accept_offer`, so the
refusals are the use case's (5.8)."""

from uuid import UUID

from django.db.models import Model, QuerySet

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_appointment_response import (
    ResponseFacts,
    decode_acceptance,
    response_resource,
)
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_search import SearchQuery
from scheduling.domain.vocabulary import Role, WaitlistStatus
from scheduling.models import Appointment, User, WaitlistEntry
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_reads import Part, SearchPage, search_part
from scheduling.use_cases.waitlist import accept_offer

REFUSED_MESSAGE = "This element cannot be accepted."


def read_response(identifier: str, caller: Caller) -> Result[Resource]:
    if caller.user is None:
        return Failure.unauthenticated()
    part = _part(caller.user)
    if part.visible().filter(pk=identifier).exists():
        return Success(part.build([UUID(identifier)])[0])
    return Failure.not_found() if caller.role is Role.ADMIN else Failure.forbidden()


def search_responses(query: SearchQuery, caller: Caller) -> Result[SearchPage]:
    if caller.user is None:
        return Failure.unauthenticated()
    return Success(search_part(_part(caller.user), query))


def create_response(body: dict[str, object], caller: Caller) -> Result[Resource]:
    user = caller.user
    if user is None:
        return Failure.unauthenticated()
    if caller.role not in (Role.PATIENT, Role.ADMIN):
        return Failure.forbidden()
    acceptance = decode_acceptance(body)
    if isinstance(acceptance, str):
        return Failure.invalid_input([FieldMessage(acceptance, REFUSED_MESSAGE)])
    patient_id = (
        WaitlistEntry.objects.filter(pk=acceptance.entry_id)
        .values_list("patient_id", flat=True)
        .first()
    )
    if patient_id is not None and patient_id != acceptance.patient_id:
        return Failure.invalid_input([FieldMessage("AppointmentResponse.actor", REFUSED_MESSAGE)])
    accepted = accept_offer(acceptance.entry_id, user)
    if isinstance(accepted, Failure):
        return accepted
    return Success(_responses([accepted.value.pk])[0])


def _part(user: User) -> Part:
    def rows() -> QuerySet[Model]:
        booked = WaitlistEntry.objects.filter(status=WaitlistStatus.BOOKED)
        if user.role == Role.ADMIN:
            return booked
        return booked.filter(patient=user) if user.role == Role.PATIENT else booked.none()

    return Part(
        visible=rows,
        everything=rows,
        id_column="pk",
        sort_columns={},
        filters={},
        build=_responses,
    )


def _responses(entry_ids: list[UUID]) -> list[Resource]:
    rows = Appointment.objects.filter(waitlist_entry_id__in=entry_ids).order_by("pk")
    return [
        response_resource(
            ResponseFacts(
                row.waitlist_entry_id,
                row.inherited_version + row.version,
                row.updated_at,
                row.patient_id,
                row.starts_at,
                row.ends_at,
            )
        )
        for row in rows
        if row.waitlist_entry_id is not None
    ]
