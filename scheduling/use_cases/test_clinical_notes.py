"""Section 9.4: clinical notes. Saved apart, private to the appointment's clinician, audited by
field name only."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from django.db import DatabaseError

from scheduling.domain.failure import Failure, FieldMessage, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, AuditLogEntry, User
from scheduling.models.builders import Clinic, make, make_clinic, model_class
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

PLANTED_NOTE = "planted-clinical-note-5521"
CONTEXT = RequestContext(correlation_id="corr-note", now=datetime(2030, 1, 7, 6, 0, tzinfo=UTC))


def _appointment(clinic: Clinic) -> Appointment:
    row = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
    )
    assert isinstance(row, Appointment)
    return row


def _clinician_of(clinic: Clinic) -> User:
    user = clinic.clinician.user
    assert isinstance(user, User)
    return user


def _save(appointment: Appointment, text: str, actor: User) -> object:
    from scheduling.use_cases.clinical_notes import save_clinical_note

    with bind_request_context(CONTEXT):
        return save_clinical_note(appointment.pk, text, actor)


def returns_note_when_own_clinician_saves_then_reads() -> None:
    from scheduling.use_cases.clinical_notes import read_clinical_note

    clinic = make_clinic()
    appointment = _appointment(clinic)
    clinician = _clinician_of(clinic)

    _save(appointment, PLANTED_NOTE, clinician)

    with bind_request_context(CONTEXT):
        assert read_clinical_note(appointment.pk, clinician) == Success(PLANTED_NOTE)


def returns_note_in_its_own_table_and_not_on_the_appointment() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)

    _save(appointment, PLANTED_NOTE, _clinician_of(clinic))

    rows = model_class("ClinicalNote")._default_manager.filter(appointment_id=appointment.pk)
    assert list(rows.values_list("clinical_notes", flat=True)) == [PLANTED_NOTE]
    assert "clinical_notes" not in {field.name for field in Appointment._meta.concrete_fields}


def returns_changed_field_name_without_content_when_note_saved() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)

    _save(appointment, PLANTED_NOTE, _clinician_of(clinic))

    entry = AuditLogEntry.objects.get(action="appointment.note_save")
    assert entry.entity_type == "Appointment"
    assert entry.entity_id == str(appointment.pk)
    assert entry.metadata["changed_fields"] == ["clinical_notes"]
    assert PLANTED_NOTE not in str(entry.metadata)


def returns_note_and_writes_second_entry_when_saved_twice() -> None:
    from scheduling.use_cases.clinical_notes import read_clinical_note

    clinic = make_clinic()
    appointment = _appointment(clinic)
    clinician = _clinician_of(clinic)
    _save(appointment, "first", clinician)

    _save(appointment, "second", clinician)

    with bind_request_context(CONTEXT):
        assert read_clinical_note(appointment.pk, clinician) == Success("second")
    assert AuditLogEntry.objects.filter(action="appointment.note_save").count() == 2


def returns_invalid_input_and_writes_nothing_when_note_is_5001_characters() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)

    result = _save(appointment, "x" * 5001, _clinician_of(clinic))

    assert result == Failure.invalid_input(
        [FieldMessage("clinical_notes", "Use at most 5000 characters.")]
    )
    assert AuditLogEntry.objects.filter(action="appointment.note_save").count() == 0


def returns_back_note_when_audit_write_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)

    def broken(*_arguments: object, **_keywords: object) -> None:
        raise DatabaseError("audit down")

    monkeypatch.setattr("scheduling.use_cases.clinical_notes.record_audit", broken)

    with pytest.raises(DatabaseError):
        _save(appointment, PLANTED_NOTE, _clinician_of(clinic))

    assert model_class("ClinicalNote")._default_manager.count() == 0


def returns_forbidden_when_admin_saves_or_reads_note() -> None:
    from scheduling.use_cases.clinical_notes import read_clinical_note, save_clinical_note

    clinic = make_clinic()
    appointment = _appointment(clinic)
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)

    with bind_request_context(CONTEXT):
        assert save_clinical_note(appointment.pk, PLANTED_NOTE, admin) == Failure.forbidden()
        assert read_clinical_note(appointment.pk, admin) == Failure.forbidden()


def returns_forbidden_when_another_clinician_saves_or_reads_note() -> None:
    from scheduling.use_cases.clinical_notes import read_clinical_note, save_clinical_note

    clinic = make_clinic()
    appointment = _appointment(clinic)
    other = _clinician_of(make_clinic())

    with bind_request_context(CONTEXT):
        assert save_clinical_note(appointment.pk, PLANTED_NOTE, other) == Failure.forbidden()
        assert read_clinical_note(appointment.pk, other) == Failure.forbidden()


def returns_forbidden_when_patient_saves_or_reads_note() -> None:
    from scheduling.use_cases.clinical_notes import read_clinical_note, save_clinical_note

    clinic = make_clinic()
    appointment = _appointment(clinic)

    with bind_request_context(CONTEXT):
        assert (
            save_clinical_note(appointment.pk, PLANTED_NOTE, clinic.patient) == Failure.forbidden()
        )
        assert read_clinical_note(appointment.pk, clinic.patient) == Failure.forbidden()


def returns_not_found_when_appointment_is_missing() -> None:
    from scheduling.use_cases.clinical_notes import save_clinical_note

    clinician = _clinician_of(make_clinic())

    with bind_request_context(CONTEXT):
        assert save_clinical_note(uuid4(), PLANTED_NOTE, clinician) == Failure.not_found()


def returns_saved_text_when_note_is_saved() -> None:
    clinic = make_clinic()

    assert _save(_appointment(clinic), PLANTED_NOTE, _clinician_of(clinic)) == Success(PLANTED_NOTE)


def returns_empty_note_when_none_was_saved() -> None:
    from scheduling.use_cases.clinical_notes import read_clinical_note

    clinic = make_clinic()

    with bind_request_context(CONTEXT):
        assert read_clinical_note(_appointment(clinic).pk, _clinician_of(clinic)) == Success("")


def returns_forbidden_when_owner_of_the_profile_is_no_longer_a_clinician() -> None:
    from scheduling.use_cases.clinical_notes import read_clinical_note, save_clinical_note

    clinic = make_clinic()
    appointment = _appointment(clinic)
    owner = _clinician_of(clinic)
    owner.role = "ADMIN"
    owner.version += 1
    owner.save()

    with bind_request_context(CONTEXT):
        assert save_clinical_note(appointment.pk, PLANTED_NOTE, owner) == Failure.forbidden()
        assert read_clinical_note(appointment.pk, owner) == Failure.forbidden()
