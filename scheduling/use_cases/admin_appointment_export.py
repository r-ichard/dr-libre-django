"""Section 13: the admin's appointment list as CSV rows, ids only. The read and its audit entry
share one transaction, so the row count in the log is the number of rows the admin received."""

from datetime import UTC, datetime
from uuid import UUID

from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.csv_cells import csv_row
from scheduling.domain.failure import Failure, Result, Success
from scheduling.models import User
from scheduling.use_cases.admin_appointments import (
    NEWEST_FIRST,
    AdminAppointmentFilters,
    matching_appointments,
)
from scheduling.use_cases.audit import AuditEvent, record_audit

EXPORT_ROW_LIMIT = 50_000
EXPORT_HEADER = [
    "appointment_id", "start", "end", "status", "source", "patient_id", "clinician_id",
    "department_id", "appointment_type_id", "room_id",
]  # fmt: skip
TOO_MANY_ROWS = (
    f"More than {EXPORT_ROW_LIMIT:,} appointments match. Narrow the days or the filters and "
    "export again."
)


def export_appointments(filters: AdminAppointmentFilters, actor: User) -> Result[list[list[str]]]:
    with transaction.atomic():
        found = list(
            matching_appointments(filters)
            .order_by(*NEWEST_FIRST)
            .values_list(
                "pk", "starts_at", "ends_at", "status", "source", "patient_id", "clinician_id",
                "appointment_type__department_id", "appointment_type_id", "room_id",
            )[: EXPORT_ROW_LIMIT + 1]
        )  # fmt: skip
        if len(found) > EXPORT_ROW_LIMIT:
            return Failure.rule_violation([TOO_MANY_ROWS])
        metadata = AuditMetadata(counts={"row_count": len(found)})
        record_audit(AuditEvent("appointment.export", "Appointment", "export", metadata), actor)
    return Success([csv_row(EXPORT_HEADER), *(_cells(row) for row in found)])


def _cells(
    row: tuple[UUID, datetime, datetime, str, str, UUID, UUID, UUID, UUID, UUID | None],
) -> list[str]:
    identifier, starts_at, ends_at, status, source, *ids = row
    cells = [str(identifier), _instant(starts_at), _instant(ends_at), status, source]
    return csv_row([*cells, *("" if other is None else str(other) for other in ids)])


def _instant(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
