"""Section 10: create, update and delete of the five admin records."""

import json
from uuid import UUID, uuid4

import pytest
from django.apps import apps
from django.db.models import Model

from scheduling.domain.failure import Failure, FailureCode, Success
from scheduling.models import AuditLogEntry, Hospital, Room, User
from scheduling.models.builders import make
from scheduling.use_cases.test_admin_record_support import (
    KINDS,
    MODEL_OF,
    _a_department,
    _an_admin,
    _an_edit,
    _create,
    _created,
    _delete,
    _edited,
    _field_messages,
    _hospital_values,
    _in_context,
    _make_existing,
    _values_for,
)

pytestmark = pytest.mark.django_db

CODE_TAKEN = "Code is taken."


def _room() -> Room:
    room = make("Room")
    assert isinstance(room, Room)
    return room


def _entries(action: str) -> list[AuditLogEntry]:
    return list(AuditLogEntry.objects.filter(action=action))


def returns_hospital_with_version_1_and_one_audit_entry_when_admin_creates_it() -> None:
    admin = _an_admin()

    result = _in_context(lambda: _create("hospital", _hospital_values(), admin))

    assert isinstance(result, Success)
    hospital = Hospital.objects.get(pk=result.value)
    assert (hospital.version, hospital.code, hospital.created_by_id) == (1, "saint-anne", admin.pk)
    [entry] = _entries("hospital.create")
    assert entry.entity_id == str(hospital.pk) and entry.actor_id == admin.pk


def returns_audit_with_field_names_and_no_free_text_when_hospital_is_created() -> None:
    admin = _an_admin()

    _created("hospital", admin)

    [entry] = _entries("hospital.create")
    assert entry.metadata["ids"] == {}
    assert sorted(entry.metadata["changed_fields"]) == sorted(_hospital_values())
    text = json.dumps(entry.metadata)
    for private in ("Saint Anne", "saint-anne", "1 Rue Neuve", "+33 1 23 45 67 89"):
        assert private not in text


def returns_parent_id_in_audit_when_department_is_created() -> None:
    admin = _an_admin()
    values = _values_for("department")

    _in_context(lambda: _create("department", values, admin))

    [entry] = _entries("department.create")
    assert entry.metadata["ids"] == {"hospital_id": str(values["hospital_id"])}


@pytest.mark.parametrize("role", ["PATIENT", "CLINICIAN"])
@pytest.mark.parametrize("kind", KINDS)
def returns_forbidden_and_writes_nothing_when_a_non_admin_creates_a_record(
    kind: str, role: str
) -> None:
    actor = make("User", role=role)
    assert isinstance(actor, User)
    values = _values_for(kind)
    before = AuditLogEntry.objects.count()

    result = _in_context(lambda: _create(kind, values, actor))

    assert result == Failure.forbidden()
    assert AuditLogEntry.objects.count() == before


@pytest.mark.parametrize("kind", KINDS)
def returns_code_taken_on_code_field_when_code_differs_only_by_case(kind: str) -> None:
    _make_existing(kind, code="taken-code")
    values = _values_for(kind, code="TAKEN-Code")

    result = _in_context(lambda: _create(kind, values, _an_admin()))

    assert [(item.field, item.message) for item in _field_messages(result)] == [
        ("code", CODE_TAKEN)
    ]


@pytest.mark.parametrize("kind", KINDS)
def returns_code_taken_when_an_edit_takes_the_code_of_another_record(kind: str) -> None:
    admin = _an_admin()
    _make_existing(kind, code="first-code")
    other_id = _created(kind, admin, code="second-code")

    result = _edited(_an_edit(kind, other_id, {"code": "FIRST-code"}, 1), admin)

    assert [item.field for item in _field_messages(result)] == ["code"]


def returns_invalid_input_and_stores_nothing_when_a_department_names_no_hospital() -> None:
    values = _values_for("department", hospital_id=None)

    result = _in_context(lambda: _create("department", values, _an_admin()))

    assert [item.field for item in _field_messages(result)] == ["hospital"]


@pytest.mark.parametrize("kind", ["room", "appointment_type"])
def returns_invalid_input_when_a_record_names_no_department(kind: str) -> None:
    values = _values_for(kind, department_id=None)

    result = _in_context(lambda: _create(kind, values, _an_admin()))

    assert [item.field for item in _field_messages(result)] == ["department"]


def returns_writes_nothing_and_keeps_version_when_edit_changes_nothing() -> None:
    admin = _an_admin()
    hospital_id = _created("hospital", admin)
    before = Hospital.objects.get(pk=hospital_id)

    result = _edited(_an_edit("hospital", hospital_id, _hospital_values(), 1), admin)

    after = Hospital.objects.get(pk=hospital_id)
    assert isinstance(result, Success)
    assert (after.version, after.updated_at) == (before.version, before.updated_at)
    assert _entries("hospital.update") == []


def raises_version_by_one_and_audits_changed_field_names_when_name_changes() -> None:
    admin = _an_admin()
    hospital_id = _created("hospital", admin)

    result = _edited(_an_edit("hospital", hospital_id, {"name": "Saint Anne North"}, 1), admin)

    assert isinstance(result, Success)
    assert Hospital.objects.get(pk=hospital_id).version == 2
    [entry] = _entries("hospital.update")
    assert entry.metadata["changed_fields"] == ["name"]
    assert "Saint Anne" not in json.dumps(entry.metadata)


def returns_conflict_and_keeps_first_save_when_edit_carries_an_older_version() -> None:
    admin = _an_admin()
    hospital_id = _created("hospital", admin)
    _edited(_an_edit("hospital", hospital_id, {"name": "First admin"}, 1), admin)

    result = _edited(_an_edit("hospital", hospital_id, {"name": "Second admin"}, 1), admin)

    assert isinstance(result, Failure) and result.code == FailureCode.CONFLICT
    stored = Hospital.objects.get(pk=hospital_id)
    assert (stored.name, stored.version) == ("First admin", 2)
    assert len(_entries("hospital.update")) == 1


def returns_not_found_when_edit_names_a_record_that_does_not_exist() -> None:
    result = _edited(_an_edit("hospital", uuid4(), {"name": "Ghost"}, 1), _an_admin())

    assert result == Failure.not_found()


def returns_invalid_input_naming_count_when_room_moves_while_two_clinicians_use_it() -> None:
    admin = _an_admin()
    room = _room()
    old_department = room.department
    for _ in range(2):
        make("ClinicianProfile", department=old_department, default_room=room)
    target = _a_department()

    result = _edited(_an_edit("room", room.pk, {"department_id": target.pk}, 1), admin)

    [message] = _field_messages(result)
    assert message.field == "department" and "2 clinicians" in message.message
    assert Room.objects.get(pk=room.pk).department_id == old_department.pk


def returns_moves_room_when_no_clinician_uses_it_as_default() -> None:
    room = _room()
    target = _a_department()

    result = _edited(_an_edit("room", room.pk, {"department_id": target.pk}, 1), _an_admin())

    assert isinstance(result, Success)
    assert Room.objects.get(pk=room.pk).department_id == target.pk


def returns_no_audit_and_no_row_when_the_audit_entry_cannot_be_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*_: object) -> None:
        raise RuntimeError("audit down")

    monkeypatch.setattr("scheduling.use_cases.admin_records.record_audit", refuse)

    with pytest.raises(RuntimeError):
        _in_context(lambda: _create("hospital", _hospital_values(), _an_admin()))

    assert Hospital.objects.count() == 0


@pytest.mark.parametrize("kind", KINDS)
def returns_success_and_audits_the_record_id_only_when_nothing_depends_on_it(kind: str) -> None:
    admin = _an_admin()
    record_id = _created(kind, admin)

    result = _in_context(lambda: _delete(kind, record_id, admin))

    assert result == Success(None)
    assert not _model(MODEL_OF[kind])._default_manager.filter(pk=record_id).exists()
    [entry] = _entries(f"{kind}.delete")
    assert (entry.entity_id, entry.metadata["changed_fields"]) == (str(record_id), [])


def _model(name: str) -> type[Model]:
    return apps.get_model("scheduling", name)


def returns_has_dependents_with_count_when_hospital_has_two_departments() -> None:
    hospital = make("Hospital")
    make("Department", hospital=hospital)
    make("Department", hospital=hospital)

    result = _in_context(lambda: _delete("hospital", hospital.pk, _an_admin()))

    assert result == Failure.has_dependents(["2 departments"])
    assert Hospital.objects.filter(pk=hospital.pk).exists()
    assert _entries("hospital.delete") == []


def returns_has_dependents_listing_every_reason_when_department_is_in_use() -> None:
    department = _a_department()
    make("Room", department=department)
    make("AppointmentType", department=department)
    make("ClinicianProfile", department=department)

    result = _in_context(lambda: _delete("department", department.pk, _an_admin()))

    assert result == Failure.has_dependents(["1 clinician", "1 room", "1 appointment type"])


def returns_has_dependents_when_a_room_is_a_clinicians_default_room() -> None:
    room = _room()
    make("ClinicianProfile", department=room.department, default_room=room)

    result = _in_context(lambda: _delete("room", room.pk, _an_admin()))

    assert result == Failure.has_dependents(["1 clinician with this default room"])


def returns_has_dependents_when_a_department_is_added_between_the_check_and_the_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hospital = make("Hospital")
    from scheduling.use_cases import admin_record_reads

    count_departments = admin_record_reads.dependent_counts

    def count_then_add_department(kind: str, record_id: UUID) -> dict[str, int]:
        counts = count_departments(kind, record_id)
        make("Department", hospital=hospital)
        return counts

    monkeypatch.setattr(admin_record_reads, "dependent_counts", count_then_add_department)

    result = _in_context(lambda: _delete("hospital", hospital.pk, _an_admin()))

    assert result == Failure.has_dependents(["1 department"])
    assert Hospital.objects.filter(pk=hospital.pk).exists()


def returns_forbidden_when_a_clinician_deletes_a_record() -> None:
    actor = make("User", role="CLINICIAN")
    assert isinstance(actor, User)
    hospital = make("Hospital")

    result = _in_context(lambda: _delete("hospital", hospital.pk, actor))

    assert result == Failure.forbidden()
    assert Hospital.objects.filter(pk=hospital.pk).exists()
