"""Task 19, section 10: attach, edit and delete a clinician profile; public search follows."""

from datetime import timedelta

import pytest

from scheduling.domain.failure import Failure, Success
from scheduling.domain.search_query import parse_search_query
from scheduling.models import AuditLogEntry, ClinicianProfile, Department, User
from scheduling.models.builders import make
from scheduling.use_cases.admin_clinicians import attach_profile, delete_profile, update_profile
from scheduling.use_cases.admin_records import RecordEdit
from scheduling.use_cases.admin_users import deactivate_user
from scheduling.use_cases.search import search_public
from scheduling.use_cases.search_types import ProviderResult
from scheduling.use_cases.test_admin_record_support import (
    NOW,
    _an_admin,
    _field_messages,
    _in_context,
)

pytestmark = pytest.mark.django_db


def _user(role: str = "CLINICIAN", **overrides: object) -> User:
    row = make("User", role=role, **overrides)
    assert isinstance(row, User)
    return row


def _department() -> Department:
    row = make("Department")
    assert isinstance(row, Department)
    return row


def _values(user: User, department: Department, **overrides: object) -> dict[str, object]:
    specialty = make("Specialty")
    return {
        "user_id": user.pk,
        "department_id": department.pk,
        "specialty_id": specialty.pk,
        "title": "Dr",
        "bio": "",
        "default_room_id": None,
        **overrides,
    }


def _attach(values: dict[str, object], actor: User) -> object:
    return _in_context(lambda: attach_profile(values, actor))


def _profile() -> ClinicianProfile:
    row = make("ClinicianProfile")
    assert isinstance(row, ClinicianProfile)
    return row


def returns_profile_with_weight_1_version_1_and_one_audit_entry_when_attached() -> None:
    admin, user, department = _an_admin(), _user(), _department()

    result = _attach(_values(user, department), admin)

    assert isinstance(result, Success)
    profile = ClinicianProfile.objects.get(pk=result.value)
    assert (profile.round_robin_weight, profile.version, profile.user_id) == (1, 1, user.pk)
    [entry] = AuditLogEntry.objects.filter(action="clinician.create")
    assert entry.metadata["ids"] == {"department_id": str(department.pk)}
    assert "Dr" not in str(entry.metadata)


@pytest.mark.parametrize("kind", ["patient", "admin", "inactive", "attached"])
def returns_message_when_the_user_is_not_an_active_clinician_without_a_profile(kind: str) -> None:
    department = _department()
    user = {
        "patient": lambda: _user("PATIENT"),
        "admin": lambda: _user("ADMIN"),
        "inactive": lambda: _user(is_active=False),
        "attached": lambda: User.objects.get(clinicianprofile__pk=_profile().pk),
    }[kind]()

    result = _attach(_values(user, department), _an_admin())

    assert [m.field for m in _field_messages(result)] == ["user"]


def returns_messages_for_an_inactive_specialty_and_a_room_of_another_department() -> None:
    department = _department()
    inactive = make("Specialty", is_active=False)
    elsewhere = make("Room")

    result = _attach(
        _values(
            _user(),
            department,
            specialty_id=inactive.pk,
            default_room_id=elsewhere.pk,
        ),
        _an_admin(),
    )

    assert {m.field for m in _field_messages(result)} == {"specialty", "default_room"}


@pytest.mark.parametrize("role", ["PATIENT", "CLINICIAN"])
def returns_forbidden_when_a_non_admin_calls_each_clinician_use_case(role: str) -> None:
    actor, profile = _user(role), _profile()

    results = [
        _attach(_values(_user(), _department()), actor),
        _in_context(lambda: update_profile(RecordEdit("c", profile.pk, {"title": "X"}, 1), actor)),
        _in_context(lambda: delete_profile(profile.pk, actor)),
    ]

    assert results == [Failure.forbidden()] * 3
    assert AuditLogEntry.objects.count() == 0


def _update(profile: ClinicianProfile, admin: User, **values: object) -> object:
    edit = RecordEdit("clinician", profile.pk, values, profile.version)
    return _in_context(lambda: update_profile(edit, admin))


def returns_new_version_and_field_names_when_the_title_changes() -> None:
    profile = _profile()

    result = _update(profile, _an_admin(), title="Prof", round_robin_weight=3)

    assert isinstance(result, Success)
    profile.refresh_from_db()
    assert (profile.title, profile.round_robin_weight, profile.version) == ("Prof", 3, 2)
    [entry] = AuditLogEntry.objects.filter(action="clinician.update")
    assert sorted(entry.metadata["changed_fields"]) == ["round_robin_weight", "title"]


def returns_no_audit_entry_when_the_edit_changes_nothing() -> None:
    profile = _profile()

    result = _update(profile, _an_admin(), title=profile.title)

    assert result == Success(profile.pk)
    assert AuditLogEntry.objects.count() == 0


def returns_conflict_when_the_version_is_old() -> None:
    profile = _profile()
    edit = RecordEdit("clinician", profile.pk, {"title": "Late"}, profile.version + 1)

    assert _in_context(lambda: update_profile(edit, _an_admin())) == Failure.conflict(["clinician"])


@pytest.mark.parametrize("weight", [0, "0", "1.5", "x", -1])
def returns_weight_message_when_the_weight_is_not_a_whole_number_of_one_or_more(
    weight: object,
) -> None:
    result = _update(_profile(), _an_admin(), round_robin_weight=weight)

    assert [m.field for m in _field_messages(result)] == ["round_robin_weight"]


def returns_three_reasons_when_the_department_moves_with_appointments_rules_and_room() -> None:
    profile = _profile()
    room = make("Room", department=profile.department)
    profile.default_room_id = room.pk
    profile.save()
    make("AvailabilityRule", clinician=profile)
    make(
        "Appointment",
        clinician=profile,
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=1, minutes=20),
    )
    profile.refresh_from_db()

    result = _update(profile, _an_admin(), department_id=_department().pk)

    assert [m.field for m in _field_messages(result)] == ["department"] * 3


def returns_has_dependents_when_a_profile_with_an_appointment_is_deleted() -> None:
    profile = _profile()
    make("Appointment", clinician=profile)

    result = _in_context(lambda: delete_profile(profile.pk, _an_admin()))

    assert result == Failure.has_dependents(["1 appointment"])
    assert ClinicianProfile.objects.filter(pk=profile.pk).exists()


def returns_success_and_audit_entry_when_deleting_a_profile_without_appointments() -> None:
    profile = _profile()

    result = _in_context(lambda: delete_profile(profile.pk, _an_admin()))

    assert result == Success(None)
    [entry] = AuditLogEntry.objects.filter(action="clinician.delete")
    assert entry.entity_id == str(profile.pk)


def returns_rollback_when_the_audit_entry_cannot_be_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("audit down")

    monkeypatch.setattr("scheduling.use_cases.admin_clinicians.record_audit", failing)

    with pytest.raises(RuntimeError):
        _attach(_values(_user(), _department()), _an_admin())

    assert ClinicianProfile.objects.count() == 0


def _provider_names() -> list[str]:
    page = search_public("providers", parse_search_query({}), NOW)
    return [r.full_name for r in page.results if isinstance(r, ProviderResult)]


def returns_clinician_in_public_search_when_the_profile_was_just_attached() -> None:
    department = _department()
    make("AppointmentType", department=department)
    user = _user(full_name="Fresh Fiona")
    assert _provider_names() == []

    result = _attach(_values(user, department), _an_admin())
    assert isinstance(result, Success)
    profile = ClinicianProfile.objects.get(pk=result.value)
    make("AvailabilityRule", clinician=profile)

    assert _provider_names() == ["Fresh Fiona"]


def returns_no_clinician_in_public_search_when_the_user_is_deactivated() -> None:
    profile = _profile()
    make("AppointmentType", department=profile.department)
    make("AvailabilityRule", clinician=profile)
    user = User.objects.get(clinicianprofile__pk=profile.pk)
    before = _provider_names()

    _in_context(lambda: deactivate_user(user.pk, user.version, _an_admin()))

    assert before == [user.full_name] and _provider_names() == []
