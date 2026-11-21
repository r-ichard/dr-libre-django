"""Section 9.4: a clinical note is private to the appointment's clinician; admins and patients
are refused. A note is saved or replaced, never listed or deleted: the spec asks for neither.
The audit entry names the field only."""

from uuid import UUID

from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.clinical_note_rules import validate_clinical_note
from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.vocabulary import Role
from scheduling.models import Appointment, ClinicalNote, User
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.record_access import guard_record

NOTE_FIELD = "clinical_notes"


def save_clinical_note(appointment_id: UUID, text: str, actor: User) -> Result[str]:
    with transaction.atomic():
        found = _own_appointment(appointment_id, actor, lock=True)
        if isinstance(found, Failure):
            return found
        checked = validate_clinical_note(text)
        if isinstance(checked, Failure):
            return checked
        appointment = found.value
        ClinicalNote.objects.update_or_create(
            appointment=appointment, defaults={NOTE_FIELD: checked.value, "created_by": actor}
        )
        metadata = AuditMetadata(
            ids={
                "appointment_id": appointment.pk,
                "patient_id": appointment.patient_id,
                "clinician_id": appointment.clinician_id,
            },
            changed_fields=changed_field_names(ClinicalNote, [NOTE_FIELD]),
        )
        record_audit(
            AuditEvent("appointment.note_save", "Appointment", str(appointment.pk), metadata),
            actor,
        )
        return Success(checked.value)


def read_clinical_note(appointment_id: UUID, actor: User) -> Result[str]:
    found = _own_appointment(appointment_id, actor, lock=False)
    if isinstance(found, Failure):
        return found
    note = ClinicalNote.objects.filter(appointment=found.value).first()
    return Success(note.clinical_notes if note else "")


def _own_appointment(appointment_id: UUID, actor: User, *, lock: bool) -> Result[Appointment]:
    query = Appointment.objects.select_related("clinician")
    if lock:
        query = query.select_for_update(of=("self",))
    appointment = query.filter(pk=appointment_id).first()
    return guard_record(appointment, lambda found: _is_its_clinician(found, actor))


def _is_its_clinician(appointment: Appointment, actor: User) -> bool:
    return actor.role == Role.CLINICIAN and appointment.clinician.user_id == actor.pk
