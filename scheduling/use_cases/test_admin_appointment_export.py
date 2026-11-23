"""Section 13: the export's read and its audit entry are one transaction."""

import pytest

from scheduling.models import AuditLogEntry
from scheduling.models.builders import make_user
from scheduling.use_cases import admin_appointment_export
from scheduling.use_cases.admin_appointment_export import export_appointments
from scheduling.use_cases.admin_appointments import AdminAppointmentFilters

pytestmark = pytest.mark.django_db


class AuditFailedError(Exception):
    """Stands in for any error of the audit write."""


def returns_no_rows_and_no_entry_when_the_audit_entry_cannot_be_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing(*_arguments: object) -> None:
        raise AuditFailedError

    monkeypatch.setattr(admin_appointment_export, "record_audit", failing)

    with pytest.raises(AuditFailedError):
        export_appointments(AdminAppointmentFilters(), make_user(role="ADMIN"))

    assert AuditLogEntry.objects.filter(action="appointment.export").count() == 0
