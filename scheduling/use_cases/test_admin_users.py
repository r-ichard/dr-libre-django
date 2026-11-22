"""Task 19, section 10: create, edit, deactivate and delete of a user, by an admin."""

import logging
from datetime import timedelta

import pytest
from django.contrib.auth.hashers import check_password

from scheduling.domain.failure import Failure, Success
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.domain.vocabulary import SessionKind
from scheduling.models import AuditLogEntry, Session, SignInLink, User
from scheduling.models.builders import make
from scheduling.use_cases.admin_records import RecordEdit
from scheduling.use_cases.admin_users import (
    create_user,
    deactivate_user,
    delete_user,
    update_user,
)
from scheduling.use_cases.session import hash_token, open_session, resolve_session
from scheduling.use_cases.sign_in_link import use_link
from scheduling.use_cases.test_admin_record_support import (
    NOW,
    _an_admin,
    _field_messages,
    _in_context,
)

pytestmark = pytest.mark.django_db

HAS_PROFILE = "This clinician has a profile. Delete the profile first."

PLANTED = "Pl4nted-Secret-9x"
UNUSABLE = "!" + "unusable"


def _user(**overrides: object) -> User:
    row = make("User", **overrides)
    assert isinstance(row, User)
    return row


def _values(**overrides: object) -> dict[str, object]:
    return {
        "full_name": "Planted Name",
        "email": "Planted.Email@Example.org",
        "role": "CLINICIAN",
        "password": PLANTED,
        **overrides,
    }


def _created(admin: User, **overrides: object) -> User:
    result = _in_context(lambda: create_user(_values(**overrides), admin))
    assert isinstance(result, Success), result
    return User.objects.get(pk=result.value)


def _edit(user: User, actor: User, **values: object) -> object:
    return _in_context(
        lambda: update_user(RecordEdit("user", user.pk, values, user.version), actor)
    )


def _entries(prefix: str = "user.") -> list[AuditLogEntry]:
    return list(AuditLogEntry.objects.filter(action__startswith=prefix))


def returns_creates_user_with_lower_case_email_hash_version_1_and_one_audit_entry() -> None:
    admin = _an_admin()

    user = _created(admin)

    assert (user.email, user.version, user.role) == ("planted.email@example.org", 1, "CLINICIAN")
    assert user.password != PLANTED and check_password(PLANTED, user.password)
    [entry] = _entries()
    assert (entry.action, entry.entity_id, entry.actor_id) == (
        "user.create",
        str(user.pk),
        admin.pk,
    )


def returns_keeps_the_password_out_of_audit_columns_and_log_lines_when_a_user_is_created(
    caplog: pytest.LogCaptureFixture,
) -> None:
    admin = _an_admin()
    caplog.set_level(logging.DEBUG)

    user = _created(admin)
    _edit(user, admin, full_name="Other Name")

    [entry] = _entries("user.create")
    stored = [entry.metadata, entry.action, entry.entity_id, entry.correlation_id]
    assert PLANTED not in str(stored) and "Planted" not in str(stored)
    assert "password" in entry.metadata["changed_fields"]
    assert PLANTED not in caplog.text
    assert not any(PLANTED in str(value) for row in User.objects.values() for value in row.values())


def returns_email_taken_when_the_email_differs_only_by_letter_case() -> None:
    admin = _an_admin()
    _created(admin)

    result = _in_context(lambda: create_user(_values(email="PLANTED.EMAIL@example.org"), admin))

    assert [(m.field, m.message) for m in _field_messages(result)] == [("email", "Email is taken.")]
    assert User.objects.filter(email__iexact="planted.email@example.org").count() == 1


@pytest.mark.parametrize("password", ["x" * 9, "x" * 73, "a\x00" + "x" * 12])
def returns_a_password_message_when_the_password_is_outside_10_to_72_characters(
    password: str,
) -> None:
    result = _in_context(lambda: create_user(_values(password=password), _an_admin()))

    assert [m.field for m in _field_messages(result)] == ["password"]


@pytest.mark.parametrize("role", ["PATIENT", "CLINICIAN"])
def returns_forbidden_and_writes_nothing_when_a_non_admin_calls_each_user_use_case(
    role: str,
) -> None:
    actor = _user(role=role)
    target = _user()

    results = [
        _in_context(lambda: create_user(_values(), actor)),
        _edit(target, actor, full_name="Changed"),
        _in_context(lambda: deactivate_user(target.pk, target.version, actor)),
        _in_context(lambda: delete_user(target.pk, actor)),
    ]

    assert results == [Failure.forbidden()] * 4
    assert _entries() == [] and User.objects.filter(pk=target.pk, is_active=True).exists()


def returns_writes_nothing_and_keeps_the_version_when_an_edit_changes_nothing() -> None:
    admin = _an_admin()
    target = _user(full_name="Same Name")

    result = _edit(target, admin, full_name="Same Name", role=target.role)

    assert result == Success(target.pk)
    target.refresh_from_db()
    assert target.version == 1 and _entries() == []


def returns_raises_the_version_and_audits_field_names_only_when_a_name_changes() -> None:
    admin = _an_admin()
    target = _user()

    _edit(target, admin, full_name="Brand New Name")

    target.refresh_from_db()
    [entry] = _entries()
    assert (target.version, entry.action) == (2, "user.update")
    assert entry.metadata["changed_fields"] == ["full_name"]
    assert "Brand" not in str(entry.metadata) and target.email not in str(entry.metadata)


def returns_conflict_and_keeps_the_first_save_when_the_second_admin_has_an_old_version() -> None:
    first, second = _an_admin(), _an_admin()
    target = _user(full_name="Original")
    stale = target.version

    _edit(target, first, full_name="First Save")
    result = _in_context(
        lambda: update_user(RecordEdit("user", target.pk, {"full_name": "Second"}, stale), second)
    )

    assert result == Failure.conflict(["user"])
    target.refresh_from_db()
    assert target.full_name == "First Save"


def _with_access(user: User) -> str:
    token = _in_context(lambda: open_session(user, SessionKind.PASSWORD, "")).token
    SignInLink.objects.create(
        token_hash=hash_token("link-" + str(user.pk)),
        patient=user,
        expires_at=NOW + timedelta(hours=1),
    )
    return token


def returns_ends_sessions_and_cancels_unused_links_when_a_user_is_deactivated() -> None:
    admin = _an_admin()
    target = _user(role="PATIENT")
    token = _with_access(target)
    used = SignInLink.objects.create(
        token_hash=hash_token("used"),
        patient=target,
        expires_at=NOW + timedelta(hours=1),
        used_at=NOW,
    )

    result = _in_context(lambda: deactivate_user(target.pk, target.version, admin))

    assert result == Success(target.pk)
    assert isinstance(_in_context(lambda: resolve_session(token)), Failure)
    assert not Session.objects.filter(user=target).exists()
    assert SignInLink.objects.filter(patient=target, cancelled_at__isnull=False).count() == 1
    used.refresh_from_db()
    assert used.cancelled_at is None
    [entry] = _entries("user.deactivate")
    assert entry.metadata["counts"] == {"session_count": 1, "link_count": 1}
    refused = _in_context(lambda: use_link("link-" + str(target.pk), ""))
    assert isinstance(refused, Failure)


def returns_keeps_upcoming_appointments_booked_when_a_clinician_is_deactivated() -> None:
    admin = _an_admin()
    profile = make("ClinicianProfile")
    make(
        "Appointment",
        clinician=profile,
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=1, minutes=15),
    )
    user = User.objects.get(clinicianprofile__pk=profile.pk)

    result = _in_context(lambda: deactivate_user(user.pk, user.version, admin))

    assert result == Success(user.pk)

    from scheduling.models import Appointment

    assert Appointment.objects.filter(clinician_id=profile.pk, status="BOOKED").count() == 1


def returns_refuses_to_deactivate_or_demote_the_own_account() -> None:
    admin, other = _an_admin(), _an_admin()

    deactivated = _in_context(lambda: deactivate_user(admin.pk, admin.version, admin))
    demoted = _edit(admin, admin, role="PATIENT")

    assert deactivated == Failure.rule_violation(["You cannot deactivate your own account."])
    assert [m.message for m in _field_messages(demoted)][0] == "You cannot change your own role."
    admin.refresh_from_db()
    assert admin.is_active and admin.role == "ADMIN" and other.is_active


def returns_new_unproven_email_and_no_access_when_the_email_changes() -> None:
    admin = _an_admin()
    target = _user(role="PATIENT", email_verified_at=NOW)
    token = _with_access(target)
    target.set_password(PLANTED)
    target.save()
    target.refresh_from_db()

    result = _edit(target, admin, email="New.Address@Example.org")

    assert isinstance(result, Success)
    target.refresh_from_db()
    assert target.email == "new.address@example.org" and target.email_verified_at is None
    assert isinstance(_in_context(lambda: resolve_session(token)), Failure)
    assert isinstance(_in_context(lambda: use_link("link-" + str(target.pk), "")), Failure)
    [entry] = _entries("user.update")
    assert entry.metadata["changed_fields"] == ["email", "email_verified_at"]
    assert "address" not in str(entry.metadata)


def returns_refuses_an_email_change_when_the_patient_has_no_password() -> None:
    target = _user(role="PATIENT", password=UNUSABLE, email_verified_at=NOW)

    result = _edit(target, _an_admin(), email="elsewhere@example.org")

    assert [m.field for m in _field_messages(result)] == ["email"]


def returns_refuses_with_reasons_when_a_role_change_contradicts_the_records() -> None:
    admin = _an_admin()
    profile = make("ClinicianProfile")
    clinician = User.objects.get(clinicianprofile__pk=profile.pk)
    patient = _user(role="PATIENT")
    make("Appointment", patient=patient)

    to_patient = _edit(clinician, admin, role="PATIENT")
    to_clinician = _edit(patient, admin, role="CLINICIAN")

    assert (
        _field_messages(to_patient)[0].message
        == "This clinician has a profile. Delete the profile first."
    )
    assert _field_messages(to_clinician)[0].message == "This patient has 1 appointment."


def returns_has_dependents_with_reasons_when_a_user_has_appointments_or_audit_entries() -> None:
    admin = _an_admin()
    patient = _user(role="PATIENT")
    make("Appointment", patient=patient)
    actor = _user(role="ADMIN")
    AuditLogEntry.objects.create(
        actor=actor,
        action="x.y",
        entity_type="X",
        entity_id="1",
        metadata={},
        correlation_id="c",
        created_at=NOW,
    )

    by_patient = _in_context(lambda: delete_user(patient.pk, admin))
    by_actor = _in_context(lambda: delete_user(actor.pk, admin))
    own = _in_context(lambda: delete_user(admin.pk, admin))

    assert by_patient == Failure.has_dependents(["1 appointment as a patient"])
    assert by_actor == Failure.has_dependents(["1 audit entry"])
    assert own == Failure.has_dependents(["your own account"])


def returns_deletes_and_audits_a_user_who_only_has_sessions_and_notifications() -> None:
    admin = _an_admin()
    target = _user(role="PATIENT")
    _with_access(target)
    make("Notification", recipient=target)

    result = _in_context(lambda: delete_user(target.pk, admin))

    assert result == Success(None)
    assert not User.objects.filter(pk=target.pk).exists()
    [entry] = _entries("user.delete")
    assert entry.entity_id == str(target.pk)


def returns_rolls_back_when_the_audit_entry_cannot_be_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _an_admin()

    def failing(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("audit down")

    monkeypatch.setattr("scheduling.use_cases.admin_users.record_audit", failing)

    with pytest.raises(RuntimeError):
        _in_context(lambda: create_user(_values(), admin))

    assert not User.objects.filter(email="planted.email@example.org").exists()


def returns_stale_version_and_keeps_the_record_when_the_expected_version_is_old() -> None:
    admin = _an_admin()
    target = _user(full_name="Original")
    edit = RecordEdit("user", target.pk, {"full_name": "Changed"}, target.version)

    result = _in_context(lambda: update_user(edit, admin, expected_version=target.version + 1))

    assert result == stale_version()
    target.refresh_from_db()
    assert target.full_name == "Original"
