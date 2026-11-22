"""Task 23a, spec 15.6: `Appointment` create and update. The body is read as one command and the
use case the screens call runs it, so the booking rules, locks, audit entries, notifications and
emails are the same. No second way to book."""

from uuid import UUID

from django.db.models import Q

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_appointment_write import (
    Book,
    ChangeStatus,
    InvalidTransition,
    Join,
    NoChange,
    Reschedule,
    decode_create,
    decode_update,
)
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.models import Appointment, AvailabilityRule, ClinicianProfile, User
from scheduling.use_cases import fhir_appointment_loading as loading
from scheduling.use_cases.appointment_changes import (
    cancel_appointment,
    change_status,
    reschedule_appointment,
)
from scheduling.use_cases.fhir_appointment_reads import read_appointment
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.use_cases.waitlist import JoinCommand, join_waitlist

REFUSED_MESSAGE = "This element cannot be accepted."
ENTRY_ORIGIN = "waitlist"


def create_appointment(body: dict[str, object], caller: Caller) -> Result[Resource]:
    user = caller.user
    if user is None:
        return Failure.unauthenticated()
    command = decode_create(body)
    if isinstance(command, str):
        return _refused(command)
    if isinstance(command, Join):
        return _join(command, user)
    return _book(command, user)


def update_appointment(
    identifier: UUID, body: dict[str, object], caller: Caller, expected_version: int | None
) -> Result[Resource]:
    user = caller.user
    if user is None:
        return Failure.unauthenticated()
    stored = read_appointment(str(identifier), caller)
    if isinstance(stored, Failure):
        return stored
    row = Appointment.objects.filter(Q(pk=identifier) | Q(waitlist_entry_id=identifier)).first()
    if row is None:
        return Failure.invalid_transition(str(stored.value.get("status")))
    command = decode_update(stored.value, body)
    if isinstance(command, str):
        return _refused(command)
    if isinstance(command, InvalidTransition):
        return Failure.invalid_transition(row.status)
    if isinstance(command, NoChange):
        return _unchanged(stored.value, expected_version)
    changed = _change(row.pk, command, user, expected_version)
    if isinstance(changed, Failure):
        return changed
    return Success(loading.booked([changed.value.waitlist_entry_id or row.pk], user.pk)[0])


def _change(
    appointment_id: UUID,
    command: Reschedule | ChangeStatus,
    user: User,
    expected_version: int | None,
) -> Result[Appointment]:
    if isinstance(command, Reschedule):
        return reschedule_appointment(appointment_id, command.starts_at, user, expected_version)
    if command.target is AppointmentStatus.CANCELLED:
        return cancel_appointment(appointment_id, command.reason, user, expected_version)
    return change_status(appointment_id, command.target, user, expected_version)


def _unchanged(stored: Resource, expected_version: int | None) -> Result[Resource]:
    meta_block = stored["meta"]
    seen = int(str(meta_block["versionId"])) if isinstance(meta_block, dict) else 0
    if expected_version is not None and expected_version != seen:
        return stale_version()
    return Success(stored)


def _book(command: Book, user: User) -> Result[Resource]:
    clinician_id = _clinician_of(command.practitioner_id, command.rule_id)
    if isinstance(clinician_id, Failure):
        return clinician_id
    placement = PlacementCommand(
        command.type_id,
        command.starts_at,
        clinician_id,
        command.patient_id,
        command.room_id,
        command.reason,
    )
    placed = place_appointment(placement, user)
    if isinstance(placed, Failure):
        return placed
    return Success(loading.booked([placed.value.pk], user.pk)[0])


def _join(command: Join, user: User) -> Result[Resource]:
    clinician_id = _clinician_of(command.practitioner_id, None)
    if isinstance(clinician_id, Failure):
        return clinician_id
    joined = join_waitlist(
        JoinCommand(
            command.type_id,
            command.earliest_at,
            command.latest_at,
            clinician_id,
            command.patient_id,
        ),
        user,
    )
    if isinstance(joined, Failure):
        return joined
    return Success(loading.waiting([joined.value.pk])[0])


def _clinician_of(practitioner_id: UUID | None, rule_id: UUID | None) -> UUID | None | Failure:
    """The profile a practitioner id or a slot's schedule names; both must agree."""
    named = None
    if practitioner_id is not None:
        named = (
            ClinicianProfile.objects.filter(user_id=practitioner_id)
            .values_list("pk", flat=True)
            .first()
        )
        if named is None:
            return Failure.not_found()
    if rule_id is None:
        return named
    owner = (
        AvailabilityRule.objects.filter(pk=rule_id).values_list("clinician_id", flat=True).first()
    )
    if owner is None:
        return Failure.not_found()
    if named is not None and named != owner:
        return _refused("Appointment.slot")
    return owner


def _refused(name: str) -> Failure:
    return Failure.invalid_input([FieldMessage(name, REFUSED_MESSAGE)])
