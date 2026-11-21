"""Section 9.3: the history of an appointment, oldest first."""

from datetime import UTC, datetime, timedelta

import pytest
from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOON = datetime(2030, 1, 7, 12, 0, tzinfo=UTC)


def _record(action: str, entity_id: str, moment: datetime) -> None:
    with bind_request_context(RequestContext("corr-history", moment)), transaction.atomic():
        record_audit(AuditEvent(action, "Appointment", entity_id, AuditMetadata(ids={})), None)


def returns_entries_of_this_appointment_oldest_first_when_written_out_of_order() -> None:
    from scheduling.use_cases.clinician_appointment import appointment_history

    clinic = make_clinic()
    row = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
    )
    assert isinstance(row, Appointment)
    _record("appointment.complete", str(row.pk), NOON + timedelta(hours=1))
    _record("appointment.check_in", str(row.pk), NOON)
    _record("appointment.check_in", "someone-else", NOON)

    actions = [entry.action for entry in appointment_history(row.pk)]

    assert actions == ["appointment.check_in", "appointment.complete"]
