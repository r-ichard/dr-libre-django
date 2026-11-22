"""Which rows the seed made and the state it left them in, one `demo_seed.mark` audit entry per
row (row id in the metadata ids, state as counts). A row that later differs from its mark was
changed by a person."""

from collections.abc import Iterable, Mapping
from datetime import datetime
from uuid import UUID

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.models import (
    Appointment,
    AuditLogEntry,
    Notification,
    TimeOff,
    WaitlistEntry,
)
from scheduling.models.booking import ClinicalNote
from scheduling.use_cases.audit import AuditEvent, record_audit

MARK_ACTION = "demo_seed.mark"
RUN_ACTION = "demo_seed.run"
APPOINTMENT_KEY = "appointment_id"
ENTRY_KEY = "waitlist_entry_id"
TIME_OFF_KEY = "time_off_id"

type Snapshot = Mapping[str, int]


def snapshot_of(row: Appointment | WaitlistEntry | TimeOff) -> Snapshot:
    """The row's version plus what hangs on it; the seed's own steps are over when it is taken."""
    state = {"version_count": row.version}
    if isinstance(row, TimeOff):
        return state
    if isinstance(row, Appointment):
        notices = Notification.objects.filter(appointment=row)
        state["note_count"] = ClinicalNote.objects.filter(appointment=row).count()
    else:
        notices = Notification.objects.filter(waitlist_entry=row)
    state["notification_count"] = notices.count()
    state["read_count"] = notices.filter(read_at__isnull=False).count()
    return state


def record_marks(
    appointments: Iterable[Appointment],
    entries: Iterable[WaitlistEntry],
    time_offs: Iterable[TimeOff],
) -> None:
    for key, rows in (
        (APPOINTMENT_KEY, appointments),
        (ENTRY_KEY, entries),
        (TIME_OFF_KEY, time_offs),
    ):
        for row in rows:
            metadata = AuditMetadata(ids={key: row.pk}, counts=snapshot_of(row))
            record_audit(AuditEvent(MARK_ACTION, "DemoSeed", str(row.pk), metadata), None)


def marks(key: str) -> dict[UUID, Snapshot]:
    """Row id to the state the seed left it in, for every row ever marked under `key`."""
    entries = AuditLogEntry.objects.filter(action=MARK_ACTION)
    return {
        UUID(metadata["ids"][key]): metadata["counts"]
        for metadata in entries.values_list("metadata", flat=True)
        if key in metadata["ids"]
    }


def world_is_current(now: datetime) -> bool:
    """True when a run entry already carries today's UTC date: one rebuild a UTC day."""
    newest = AuditLogEntry.objects.filter(action=RUN_ACTION).order_by("-created_at").first()
    return newest is not None and newest.created_at.date() == now.date()
