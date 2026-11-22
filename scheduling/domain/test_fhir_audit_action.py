"""Task 24a, point 1: `AuditEvent.action` is a code of the R4 value set AuditEventAction."""

import pytest

from scheduling.domain.audit_labels import AUDIT_LABELS
from scheduling.domain.fhir_audit_action import audit_action_code, product_actions_of

AUDIT_EVENT_ACTION_CODES = {"C", "R", "U", "D", "E"}


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("appointment.book", "C"),
        ("time_off.create", "C"),
        ("waitlist.join", "C"),
        ("appointment.cancel", "U"),
        ("appointment.reschedule", "U"),
        ("profile.update", "U"),
        ("time_off.delete", "D"),
        ("hospital.delete", "D"),
        ("notification.read", "R"),
        ("appointment.export", "R"),
        ("auth.login_failed", "E"),
        ("reminder.run", "E"),
    ],
)
def returns_the_expected_code_when_action_is_named(action: str, expected: str) -> None:
    assert audit_action_code(action) == expected


def returns_a_code_for_every_action_the_product_writes() -> None:
    unmapped = {
        action
        for action in AUDIT_LABELS
        if audit_action_code(action) not in AUDIT_EVENT_ACTION_CODES
    }

    assert unmapped == set()


def returns_execute_when_action_is_unknown() -> None:
    assert audit_action_code("something.new") == "E"


def returns_named_actions_and_suffixes_of_the_code_when_inverted() -> None:
    showing = product_actions_of("U")

    assert "appointment.cancel" in showing.named
    assert "appointment.book" not in showing.named
    assert showing.suffixes == (".update",)
    assert "appointment.book" in showing.claimed_elsewhere
    assert "appointment.cancel" not in showing.claimed_elsewhere
    assert not showing.is_remainder


def returns_the_remainder_marker_only_for_execute_when_inverted() -> None:
    assert product_actions_of("E").is_remainder
    assert not product_actions_of("C").is_remainder
    assert product_actions_of("E").named == ()
