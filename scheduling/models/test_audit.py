"""Section 3 and 4: audit log entries are never changed or deleted, by anyone, in the database."""

from uuid import UUID

import pytest
from django.db import DatabaseError, connection, transaction

from scheduling.models.builders import change_and_save, field_of, make, model_class

pytestmark = pytest.mark.django_db
# Never use transaction=True here: its teardown flush would TRUNCATE the audit table.

TABLE = "scheduling_auditlogentry"


def _run_refused(statement: str, *parameters: UUID) -> None:
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(statement, list(parameters))


def returns_entry_when_appended_without_an_actor() -> None:
    entry = make("AuditLogEntry")

    stored = model_class("AuditLogEntry")._default_manager.get(pk=entry.pk)
    assert field_of(stored, "actor_id") is None
    assert field_of(stored, "action") == "appointment.booked"


def returns_entry_when_appended_with_an_actor() -> None:
    actor = make("User")

    entry = make("AuditLogEntry", actor=actor)

    assert (
        field_of(model_class("AuditLogEntry")._default_manager.get(pk=entry.pk), "actor_id")
        == actor.pk
    )


def rejects_update_when_audit_entry_is_changed_through_save() -> None:
    entry = make("AuditLogEntry")

    with pytest.raises(DatabaseError), transaction.atomic():
        change_and_save(entry, "action", "tampered")


def rejects_update_when_audit_entries_are_changed_through_queryset() -> None:
    make("AuditLogEntry")

    with pytest.raises(DatabaseError), transaction.atomic():
        model_class("AuditLogEntry")._default_manager.update(action="tampered")


def rejects_update_when_audit_entry_is_changed_through_raw_sql() -> None:
    entry = make("AuditLogEntry")

    _run_refused(f"UPDATE {TABLE} SET action = 'tampered' WHERE id = %s", entry.pk)  # noqa: S608


def rejects_delete_when_audit_entry_is_removed_through_the_orm() -> None:
    entry = make("AuditLogEntry")

    with pytest.raises(DatabaseError), transaction.atomic():
        entry.delete()


def rejects_delete_when_audit_entry_is_removed_through_raw_sql() -> None:
    entry = make("AuditLogEntry")

    _run_refused(f"DELETE FROM {TABLE} WHERE id = %s", entry.pk)  # noqa: S608


def rejects_truncate_when_audit_table_is_emptied() -> None:
    entry = make("AuditLogEntry")
    # Pending deferred foreign key checks make PostgreSQL refuse TRUNCATE for an unrelated reason.
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    with (
        pytest.raises(DatabaseError, match="append-only"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(f"TRUNCATE {TABLE}")

    assert model_class("AuditLogEntry")._default_manager.filter(pk=entry.pk).exists()


def returns_entry_unchanged_when_read_after_refused_update() -> None:
    entry = make("AuditLogEntry")
    with pytest.raises(DatabaseError), transaction.atomic():
        change_and_save(entry, "action", "tampered")

    stored = model_class("AuditLogEntry")._default_manager.get(pk=entry.pk)

    assert field_of(stored, "action") == "appointment.booked"
