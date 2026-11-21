"""Section 9.3: one appointment of the signed-in clinician, and its history. Someone else's
appointment is forbidden and a missing one is not found, so a page can tell them apart."""

from uuid import UUID

from scheduling.domain.failure import Result
from scheduling.domain.vocabulary import Role
from scheduling.models import Appointment, AuditLogEntry, User
from scheduling.use_cases.record_access import guard_record


def own_appointment_of_clinician(appointment_id: UUID, actor: User) -> Result[Appointment]:
    appointment = (
        Appointment.objects.select_related(
            "patient", "clinician__user", "appointment_type__department__hospital", "room"
        )
        .filter(pk=appointment_id)
        .first()
    )
    return guard_record(
        appointment,
        lambda found: actor.role == Role.CLINICIAN and found.clinician.user_id == actor.pk,
    )


def appointment_history(appointment_id: UUID) -> list[AuditLogEntry]:
    """Oldest first. Callers show the action, the time and the actor, never the metadata."""
    return list(
        AuditLogEntry.objects.select_related("actor")
        .filter(entity_type="Appointment", entity_id=str(appointment_id))
        .order_by("created_at", "pk")
    )
