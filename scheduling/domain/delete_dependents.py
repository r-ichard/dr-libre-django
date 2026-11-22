"""Section 10: what blocks deleting a record. A pure decision over counts the use case read."""

from collections.abc import Mapping
from dataclasses import dataclass

REASONS_BY_KIND = {
    "hospital": ("departments",),
    "department": ("clinicians", "rooms", "appointment_types"),
    "specialty": ("clinicians",),
    "room": ("appointments", "availability_rules", "default_room_clinicians"),
    "appointment_type": ("appointments", "waitlist_entries"),
    "user": (
        "own_account",
        "appointments_as_patient",
        "appointments_as_clinician",
        "audit_entries",
        "clinician_profile",
        "waitlist_entries",
    ),
    "clinician": ("appointments",),
}


@dataclass(frozen=True)
class Dependent:
    reason: str
    count: int


def delete_refusal(kind: str, counts: Mapping[str, int]) -> tuple[Dependent, ...]:
    """Empty when the record can go. An unknown kind raises: it is a caller's broken invariant."""
    return tuple(
        Dependent(reason, counts[reason]) for reason in REASONS_BY_KIND[kind] if counts[reason] > 0
    )
