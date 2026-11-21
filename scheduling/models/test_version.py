"""Section 15.1: every FHIR-backed row carries a version that starts at 1 and grows by one."""

from datetime import time

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import F

from scheduling.models.builders import change_and_save, field_of, make, model_class

pytestmark = pytest.mark.django_db
# Never use transaction=True here: its teardown flush would TRUNCATE the audit table.

SAVEABLE_MODELS = [
    "Hospital",
    "Department",
    "Specialty",
    "User",
    "ClinicianProfile",
    "Room",
    "AppointmentType",
    "AvailabilityRule",
    "TimeOff",
    "Appointment",
    "WaitlistEntry",
    "BookingHold",
    "Notification",
]
VERSIONED_MODELS = [*SAVEABLE_MODELS, "AuditLogEntry"]
UNVERSIONED_MODELS = ["Session", "VerificationCode", "SignInLink"]


def _stored_version(model_name: str, row_id: object) -> object:
    return field_of(model_class(model_name)._default_manager.get(pk=row_id), "version")


def _version_of(row: object) -> object:
    return field_of(row, "version")  # type: ignore[arg-type]


def _refused_update(model_name: str, row_id: object, **changes: object) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        model_class(model_name)._default_manager.filter(pk=row_id).update(**changes)


@pytest.mark.parametrize("model_name", VERSIONED_MODELS)
def returns_version_1_when_row_is_inserted(model_name: str) -> None:
    row = make(model_name)

    assert _stored_version(model_name, row.pk) == 1


def rejects_version_5_when_row_is_inserted() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make("Hospital", version=5)


def rejects_version_0_when_row_is_inserted() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make("Hospital", version=0)


@pytest.mark.parametrize("model_name", SAVEABLE_MODELS)
def returns_version_2_when_row_is_saved_once(model_name: str) -> None:
    row = make(model_name)

    row.save()

    assert _stored_version(model_name, row.pk) == 2


@pytest.mark.parametrize("model_name", SAVEABLE_MODELS)
def returns_version_3_when_row_is_saved_twice(model_name: str) -> None:
    row = make(model_name)
    row.save()

    row.save()

    assert _stored_version(model_name, row.pk) == 3


def returns_version_2_and_new_value_when_row_is_saved_with_only_one_field_named() -> None:
    row = make("Hospital")
    row.city = "Hamburg"  # type: ignore[attr-defined]

    row.save(update_fields=["city"])

    stored = model_class("Hospital")._default_manager.get(pk=row.pk)
    assert field_of(stored, "city") == "Hamburg"
    assert field_of(stored, "version") == 2


def returns_version_1_when_new_instance_with_explicit_id_is_saved() -> None:
    template = make("Hospital")
    model = model_class("Hospital")
    fresh = model(
        id=model._meta.pk.default(),
        name="Fresh",
        code="fresh-explicit",
        street_address="1 Road",
        postal_code="1",
        city="Berlin",
        country="DE",
        phone="1",
        time_zone="Europe/Berlin",
    )

    fresh.save()

    assert template.pk != fresh.pk
    assert _stored_version("Hospital", fresh.pk) == 1


def rejects_update_when_queryset_update_does_not_grow_version() -> None:
    row = make("Hospital")

    _refused_update("Hospital", row.pk, name="Renamed")

    assert _stored_version("Hospital", row.pk) == 1


def returns_version_plus_one_when_queryset_update_grows_it_by_one() -> None:
    row = make("Hospital")

    model_class("Hospital")._default_manager.filter(pk=row.pk).update(
        name="Renamed", version=F("version") + 1
    )

    assert _stored_version("Hospital", row.pk) == 2


def rejects_update_when_version_grows_by_two() -> None:
    row = make("Hospital")

    _refused_update("Hospital", row.pk, version=F("version") + 2)

    assert _stored_version("Hospital", row.pk) == 1


def rejects_update_when_version_is_lowered() -> None:
    row = make("Hospital")
    row.save()

    _refused_update("Hospital", row.pk, version=1)

    assert _stored_version("Hospital", row.pk) == 2


def rejects_save_when_row_was_changed_since_it_was_loaded() -> None:
    row = make("Hospital")
    first = model_class("Hospital")._default_manager.get(pk=row.pk)
    second = model_class("Hospital")._default_manager.get(pk=row.pk)
    change_and_save(first, "name", "First writer")

    with pytest.raises(IntegrityError), transaction.atomic():
        change_and_save(second, "name", "Second writer")

    stored = model_class("Hospital")._default_manager.get(pk=row.pk)
    assert field_of(stored, "name") == "First writer"
    assert field_of(stored, "version") == 2


def returns_in_memory_version_unchanged_when_save_is_refused() -> None:
    row = make("Hospital")
    other = model_class("Hospital")._default_manager.get(pk=row.pk)
    other.save()

    with pytest.raises(IntegrityError), transaction.atomic():
        row.save()

    assert _version_of(row) == 1


def returns_zero_rows_when_update_filters_on_a_stale_version() -> None:
    row = make("Hospital")
    row.save()

    changed = (
        model_class("Hospital")
        ._default_manager.filter(pk=row.pk, version=1)
        .update(name="Late", version=F("version") + 1)
    )

    assert changed == 0


def rejects_raw_sql_update_when_version_is_not_incremented() -> None:
    row = make("Hospital")

    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE scheduling_hospital SET name = 'x' WHERE id = %s", [row.pk])

    assert _stored_version("Hospital", row.pk) == 1


@pytest.mark.parametrize("model_name", UNVERSIONED_MODELS)
def returns_no_version_column_when_session_code_and_link_models_are_inspected(
    model_name: str,
) -> None:
    names = [field.name for field in model_class(model_name)._meta.concrete_fields]

    assert "version" not in names


def returns_version_trigger_on_every_versioned_table_when_schema_is_read() -> None:
    tables = [model_class(name)._meta.db_table for name in VERSIONED_MODELS]

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE t.tgname = 'scheduling_enforce_version' AND NOT t.tgisinternal"
        )
        guarded = {name for (name,) in cursor.fetchall()}

    assert sorted(set(tables) - guarded) == []


def returns_version_trigger_on_every_model_with_a_version_column_when_models_are_walked() -> None:
    from django.apps import apps

    with_column = {
        model._meta.db_table
        for model in apps.get_app_config("scheduling").get_models()
        if "version" in [field.name for field in model._meta.concrete_fields]
    }

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE t.tgname = 'scheduling_enforce_version' AND NOT t.tgisinternal"
        )
        guarded = {name for (name,) in cursor.fetchall()}

    assert len(with_column) == 14
    assert sorted(with_column - guarded) == []


# Parent versions: PractitionerRole is built from the profile plus its schedule rows.


@pytest.mark.parametrize("child", ["TimeOff", "AvailabilityRule"])
def returns_parent_version_plus_one_when_schedule_row_is_added(child: str) -> None:
    profile = make("ClinicianProfile")

    make(child, clinician=profile)

    assert _stored_version("ClinicianProfile", profile.pk) == 2


@pytest.mark.parametrize("child", ["TimeOff", "AvailabilityRule"])
def returns_parent_version_plus_one_when_schedule_row_is_changed(child: str) -> None:
    profile = make("ClinicianProfile")
    row = make(child, clinician=profile)

    row.save()

    assert _stored_version("ClinicianProfile", profile.pk) == 3


@pytest.mark.parametrize("child", ["TimeOff", "AvailabilityRule"])
def returns_parent_version_plus_one_when_schedule_row_is_deleted(child: str) -> None:
    profile = make("ClinicianProfile")
    row = make(child, clinician=profile)

    row.delete()

    assert _stored_version("ClinicianProfile", profile.pk) == 3


@pytest.mark.parametrize("child", ["TimeOff", "AvailabilityRule"])
def returns_parent_version_unchanged_when_other_clinician_schedule_row_changes(
    child: str,
) -> None:
    profile = make("ClinicianProfile")
    other_row = make(child)

    other_row.save()

    assert _stored_version("ClinicianProfile", profile.pk) == 1


@pytest.mark.parametrize("child", ["TimeOff", "AvailabilityRule"])
def returns_both_parent_versions_plus_one_when_schedule_row_moves_to_another_clinician(
    child: str,
) -> None:
    old_profile = make("ClinicianProfile")
    new_profile = make("ClinicianProfile")
    row = make(child, clinician=old_profile)

    change_and_save(row, "clinician", new_profile)

    assert _stored_version("ClinicianProfile", old_profile.pk) == 3
    assert _stored_version("ClinicianProfile", new_profile.pk) == 2


def returns_parent_version_plus_row_count_when_one_statement_changes_many_rows() -> None:
    profile = make("ClinicianProfile")
    for weekday in (1, 2, 3):
        make("AvailabilityRule", clinician=profile, weekday=weekday)
    before = _stored_version("ClinicianProfile", profile.pk)
    assert before == 4

    model_class("AvailabilityRule")._default_manager.filter(clinician=profile).update(
        end_time=time(16, 0), version=F("version") + 1
    )

    assert _stored_version("ClinicianProfile", profile.pk) == 7


# Practitioner is built from the user and the profile title.


def returns_user_version_plus_one_when_profile_title_changes() -> None:
    profile = make("ClinicianProfile")
    user_id = field_of(profile, "user_id")

    change_and_save(profile, "title", "Prof")

    assert _stored_version("User", user_id) == 3


def returns_user_version_plus_one_when_profile_is_added() -> None:
    user = make("User", role="CLINICIAN")

    make("ClinicianProfile", user=user)

    assert _stored_version("User", user.pk) == 2


def returns_user_version_plus_one_when_profile_is_deleted() -> None:
    profile = make("ClinicianProfile")
    user_id = field_of(profile, "user_id")

    profile.delete()

    assert _stored_version("User", user_id) == 3


def returns_user_version_unchanged_when_profile_bio_changes() -> None:
    profile = make("ClinicianProfile")
    user_id = field_of(profile, "user_id")

    change_and_save(profile, "bio", "New biography")

    assert _stored_version("User", user_id) == 2


def returns_user_version_unchanged_when_profile_of_other_clinician_changes() -> None:
    profile = make("ClinicianProfile")
    user_id = field_of(profile, "user_id")
    other = make("ClinicianProfile")

    change_and_save(other, "title", "Prof")

    assert _stored_version("User", user_id) == 2


def rejects_save_when_user_was_loaded_before_profile_title_changed() -> None:
    profile = make("ClinicianProfile")
    user = model_class("User")._default_manager.get(pk=field_of(profile, "user_id"))
    change_and_save(profile, "title", "Prof")

    with pytest.raises(IntegrityError), transaction.atomic():
        change_and_save(user, "full_name", "Late Writer")


# Specialty list: one CodeSystem and one ValueSet over all rows, revision never falls.


def _specialty_revision() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT last_value FROM scheduling_specialty_revision")
        row = cursor.fetchone()
    assert row is not None
    return int(row[0])


def returns_revision_one_when_specialty_has_never_changed() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT last_value, is_called FROM scheduling_specialty_revision")
        row = cursor.fetchone()

    assert row == (1, True)


def returns_larger_revision_when_specialty_is_added() -> None:
    before = _specialty_revision()

    make("Specialty")

    assert _specialty_revision() > before


def returns_larger_revision_when_specialty_is_changed() -> None:
    row = make("Specialty")
    before = _specialty_revision()

    change_and_save(row, "name", "Renamed")

    assert _specialty_revision() > before


def returns_larger_revision_when_specialty_is_deleted() -> None:
    row = make("Specialty")
    before = _specialty_revision()

    row.delete()

    assert _specialty_revision() > before
