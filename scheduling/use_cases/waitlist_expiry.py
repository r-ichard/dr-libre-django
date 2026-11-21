"""Section 5.8: a waiting entry past its latest time expires; an offer whose slot passed or was
taken goes back to waiting while the window is open, and expires once it is closed."""

from django.db import transaction

from scheduling.domain.appointment_status import ACTIVE_STATUSES
from scheduling.domain.vocabulary import WaitlistStatus
from scheduling.domain.waitlist_rules import ExpiryDecision, WaitlistSnapshot, expiry_decision
from scheduling.models import Appointment, WaitlistEntry
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.waitlist import audit_waitlist_change

ACTION_BY_DECISION = {
    ExpiryDecision.EXPIRE: "waitlist.expire",
    ExpiryDecision.RELEASE: "waitlist.release",
}


def expire_waitlist() -> int:
    now = current_request_context().now
    changed = 0
    with transaction.atomic():
        open_entries = (
            WaitlistEntry.objects.select_for_update(of=("self",))
            .filter(status__in=[WaitlistStatus.WAITING, WaitlistStatus.OFFERED])
            .select_related("offered_appointment")
        )
        for entry in open_entries:
            decision = expiry_decision(_snapshot_of(entry), now)
            if decision != ExpiryDecision.KEEP:
                _apply(entry, decision)
                changed += 1
    return changed


def _snapshot_of(entry: WaitlistEntry) -> WaitlistSnapshot:
    offered = entry.offered_appointment
    return WaitlistSnapshot(
        WaitlistStatus(entry.status),
        entry.latest_at,
        offered.starts_at if offered is not None else None,
        offered is not None and _is_taken(offered),
    )


def _is_taken(offered: Appointment) -> bool:
    return (
        Appointment.objects.filter(
            clinician_id=offered.clinician_id,
            status__in=ACTIVE_STATUSES,
            starts_at__lt=offered.ends_at,
            ends_at__gt=offered.starts_at,
        )
        .exclude(pk=offered.pk)
        .exists()
    )


def _apply(entry: WaitlistEntry, decision: ExpiryDecision) -> None:
    entry.status = (
        WaitlistStatus.EXPIRED if decision == ExpiryDecision.EXPIRE else WaitlistStatus.WAITING
    )
    entry.offered_appointment = None
    entry.save()
    audit_waitlist_change(
        ACTION_BY_DECISION[decision], entry, None, ["status", "offered_appointment"]
    )
