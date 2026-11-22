"""Retires the seeded world before a rebuild, sparing what a person used.

A seeded row stays when its state differs from its mark, when an unmarked row depends on it,
or when a kept row needs it (checked to a fixed point). Unmarked rows are never changed."""

from collections import Counter
from collections.abc import Mapping
from uuid import UUID

from django.db.models import Q

from scheduling.demo_seed import booking, marker
from scheduling.models import Appointment, Notification, TimeOff, WaitlistEntry
from scheduling.models.booking import ClinicalNote
from scheduling.use_cases.time_off import delete_time_off


def retire_time_off() -> Counter[str]:
    """Deletes unchanged seeded time off through its use case; counts what it kept."""
    kept: Counter[str] = Counter()
    for row_id, mark in marker.marks(marker.TIME_OFF_KEY).items():
        row = TimeOff.objects.filter(pk=row_id).select_related("clinician__user").first()
        if row is None:
            continue
        if row.version == mark["version_count"]:
            booking.expect(delete_time_off(row.pk, row.clinician.user))
        else:
            kept[TimeOff.__name__] += 1
    return kept


def retire_world() -> Counter[str]:
    """Deletes the seeded rows nobody used, children first because every relation is PROTECT."""
    appointment_marks = marker.marks(marker.APPOINTMENT_KEY)
    entry_marks = marker.marks(marker.ENTRY_KEY)
    live_appointments = {
        row.pk: row for row in Appointment.objects.filter(pk__in=appointment_marks)
    }
    live_entries = {row.pk: row for row in WaitlistEntry.objects.filter(pk__in=entry_marks)}
    kept_appointments = _changed_ids(live_appointments, appointment_marks)
    kept_entries = _changed_ids(live_entries, entry_marks)
    kept_entries |= set(
        Appointment.objects.filter(waitlist_entry__in=live_entries)
        .exclude(pk__in=appointment_marks)
        .values_list("waitlist_entry_id", flat=True)
    )
    kept_appointments |= set(
        WaitlistEntry.objects.filter(offered_appointment__in=live_appointments)
        .exclude(pk__in=entry_marks)
        .values_list("offered_appointment_id", flat=True)
    )
    _close_over(kept_appointments, kept_entries, set(live_appointments), set(live_entries))

    doomed_appointments = Appointment.objects.filter(
        pk__in=set(live_appointments) - kept_appointments
    )
    doomed_entries = WaitlistEntry.objects.filter(pk__in=set(live_entries) - kept_entries)
    Notification.objects.filter(
        Q(appointment__in=doomed_appointments) | Q(waitlist_entry__in=doomed_entries)
    ).delete()
    ClinicalNote.objects.filter(appointment__in=doomed_appointments).delete()
    # Delete order: a booking made by accepting an entry, the entry, then the slot it was offered.
    doomed_appointments.filter(waitlist_entry__isnull=False).delete()
    doomed_entries.delete()
    doomed_appointments.delete()
    return Counter(
        {Appointment.__name__: len(kept_appointments), WaitlistEntry.__name__: len(kept_entries)}
    )


def _changed_ids(
    live_rows: Mapping[UUID, Appointment] | Mapping[UUID, WaitlistEntry],
    row_marks: Mapping[UUID, marker.Snapshot],
) -> set[UUID]:
    """Ids of seeded rows whose state no longer matches the mark the seed left."""
    return {
        row_id for row_id, row in live_rows.items() if marker.snapshot_of(row) != row_marks[row_id]
    }


def _close_over(
    kept_appointments: set[UUID],
    kept_entries: set[UUID],
    seeded_appointments: set[UUID],
    seeded_entries: set[UUID],
) -> None:
    """Grows both kept sets with every seeded row a kept row points to or is pointed to by."""
    while True:
        size_before = len(kept_appointments) + len(kept_entries)
        offered = WaitlistEntry.objects.filter(pk__in=kept_entries)
        accepted = Appointment.objects.filter(pk__in=kept_appointments)
        kept_appointments |= set(offered.values_list("offered_appointment_id", flat=True))
        kept_appointments |= set(
            Appointment.objects.filter(waitlist_entry__in=kept_entries).values_list("pk", flat=True)
        )
        kept_entries |= set(accepted.values_list("waitlist_entry_id", flat=True))
        notices = Notification.objects.filter(
            Q(appointment__in=kept_appointments) | Q(waitlist_entry__in=kept_entries)
        )
        for appointment_id, entry_id in notices.values_list("appointment_id", "waitlist_entry_id"):
            kept_appointments.add(appointment_id)
            kept_entries.add(entry_id)
        kept_appointments &= seeded_appointments
        kept_entries &= seeded_entries
        if len(kept_appointments) + len(kept_entries) == size_before:
            return
