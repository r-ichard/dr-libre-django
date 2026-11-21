"""Section 3 preamble: opaque time-ordered identifiers, UTC instants, creator."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from scheduling.models.builders import change_and_save, field_of, make, model_class

pytestmark = pytest.mark.django_db


def returns_uuid_version_7_primary_key_when_record_is_saved() -> None:
    row = make("Hospital")

    assert isinstance(row.pk, uuid.UUID)
    assert row.pk.version == 7


def returns_utc_aware_creation_time_when_record_is_saved() -> None:
    before = datetime.now(UTC)

    row = make("Hospital")

    stored = model_class("Hospital")._default_manager.get(pk=row.pk)
    created_at = field_of(stored, "created_at")
    assert isinstance(created_at, datetime)
    assert created_at.utcoffset() == timedelta(0)
    assert before <= created_at <= datetime.now(UTC)


def returns_later_update_time_when_record_is_saved_again() -> None:
    row = make("Hospital")
    first_update = field_of(row, "updated_at")
    assert isinstance(first_update, datetime)

    change_and_save(row, "name", "Renamed Hospital")

    second_update = field_of(model_class("Hospital")._default_manager.get(pk=row.pk), "updated_at")
    assert isinstance(second_update, datetime)
    assert second_update > first_update


def returns_unchanged_creation_time_when_record_is_saved_again() -> None:
    row = make("Hospital")
    created_at = field_of(row, "created_at")

    change_and_save(row, "name", "Renamed Hospital")

    assert (
        field_of(model_class("Hospital")._default_manager.get(pk=row.pk), "created_at")
        == created_at
    )


def returns_empty_creator_when_no_signed_in_user_created_the_record() -> None:
    row = make("Hospital")

    assert (
        field_of(model_class("Hospital")._default_manager.get(pk=row.pk), "created_by_id") is None
    )


def returns_creator_when_a_signed_in_user_created_the_record() -> None:
    creator = make("User", role="ADMIN")

    row = make("Hospital", created_by=creator)

    assert (
        field_of(model_class("Hospital")._default_manager.get(pk=row.pk), "created_by_id")
        == creator.pk
    )
