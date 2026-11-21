"""Task 04b, section 4: the audit writer, same transaction in both directions."""

from datetime import UTC, datetime

import pytest
from django.db import DatabaseError, transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.request_context import RequestContext
from scheduling.models import AuditLogEntry, Specialty, User
from scheduling.models.builders import make
from scheduling.use_cases.audit import (
    AuditEvent,
    TransactionRequired,
    changed_field_names,
    record_audit,
)
from scheduling.use_cases.request_context import bind_request_context

INSTANT = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
CONTEXT = RequestContext(correlation_id="corr-123", now=INSTANT)
ACTION_TOO_LONG = "a" * 101


def _event(action: str = "specialty.renamed") -> AuditEvent:
    return AuditEvent(
        action=action,
        entity_type="Specialty",
        entity_id="abc",
        metadata=AuditMetadata(counts={"row_count": 1}),
    )


def _rename_specialty(specialty: Specialty, name: str, audit_action: str) -> None:
    with transaction.atomic():
        specialty.name = name
        specialty.save()
        record_audit(_event(audit_action), None)


def _rename_specialty_then_violate(specialty: Specialty, other_code: str) -> None:
    with transaction.atomic():
        record_audit(_event(), None)
        specialty.code = other_code
        specialty.save()


@pytest.mark.django_db
def returns_entry_with_context_values_when_recorded_inside_transaction() -> None:
    with bind_request_context(CONTEXT), transaction.atomic():
        record_audit(_event(), None)

    entry = AuditLogEntry.objects.get()
    assert entry.correlation_id == "corr-123"
    assert entry.created_at == INSTANT
    assert entry.actor_id is None
    assert entry.action == "specialty.renamed"
    assert entry.entity_type == "Specialty"
    assert entry.entity_id == "abc"
    assert entry.metadata == _event().metadata.to_json()


@pytest.mark.django_db
def returns_entry_with_actor_when_actor_is_given() -> None:
    actor = make("User")
    assert isinstance(actor, User)

    with bind_request_context(CONTEXT), transaction.atomic():
        record_audit(_event(), actor)

    assert AuditLogEntry.objects.get().actor_id == actor.pk


def raises_transaction_required_when_recorded_outside_transaction() -> None:
    with bind_request_context(CONTEXT), pytest.raises(TransactionRequired):
        record_audit(_event(), None)


@pytest.mark.django_db
def raises_lookup_error_when_no_request_context_is_bound() -> None:
    with pytest.raises(LookupError), transaction.atomic():
        record_audit(_event(), None)


# Never use transaction=True here: its teardown flush would TRUNCATE the audit table. The use
# case's atomic block is a savepoint inside the test transaction and rolls back the same way.
@pytest.mark.django_db
def returns_unchanged_row_when_audit_write_fails() -> None:
    specialty = make("Specialty", name="Before")
    assert isinstance(specialty, Specialty)

    with bind_request_context(CONTEXT), pytest.raises(DatabaseError):
        _rename_specialty(specialty, "After", ACTION_TOO_LONG)

    assert Specialty.objects.get(pk=specialty.pk).name == "Before"


@pytest.mark.django_db
def returns_no_audit_entry_when_change_fails() -> None:
    first = make("Specialty", code="first-code")
    second = make("Specialty", code="second-code")
    assert isinstance(first, Specialty)
    assert isinstance(second, Specialty)
    before = AuditLogEntry.objects.count()

    with bind_request_context(CONTEXT), pytest.raises(DatabaseError):
        _rename_specialty_then_violate(first, "second-code")

    assert AuditLogEntry.objects.count() == before


def returns_field_names_when_model_has_those_fields() -> None:
    names = changed_field_names(Specialty, ["name", "code"])

    assert list(names) == ["name", "code"]


def rejects_field_name_when_model_has_no_such_field() -> None:
    with pytest.raises(ValueError):
        changed_field_names(Specialty, ["patient_phone"])
