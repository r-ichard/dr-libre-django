"""Task 18, section 10: a dependent that appears after the count and before the delete."""

from uuid import UUID

import pytest
from pytest import MonkeyPatch

from scheduling.domain.failure import Failure
from scheduling.models import AuditLogEntry, Department, Hospital
from scheduling.models.builders import make
from scheduling.use_cases import admin_record_reads
from scheduling.use_cases.test_admin_record_support import _an_admin, _delete, _in_context

pytestmark = pytest.mark.django_db


def returns_has_dependents_when_a_department_appears_between_count_and_delete(
    monkeypatch: MonkeyPatch,
) -> None:
    hospital = make("Hospital")
    assert isinstance(hospital, Hospital)
    admin = _an_admin()
    real_counts = admin_record_reads.dependent_counts
    calls: list[int] = []

    def counts_then_insert(kind: str, record_id: UUID) -> dict[str, int]:
        counted = real_counts(kind, record_id)
        if not calls:
            make("Department", hospital=hospital)
        calls.append(1)
        return counted

    monkeypatch.setattr(admin_record_reads, "dependent_counts", counts_then_insert)

    result = _in_context(lambda: _delete("hospital", hospital.pk, admin))

    assert result == Failure.has_dependents(["1 department"])
    assert Department.objects.filter(hospital=hospital).count() == 1
    assert not AuditLogEntry.objects.filter(action="hospital.delete").exists()
    assert len(calls) == 2
