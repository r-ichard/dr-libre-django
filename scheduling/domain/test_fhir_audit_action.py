"""Task 24a, point 1: `AuditEvent.action` is a code of the R4 value set AuditEventAction."""

import pytest

from scheduling.domain.audit_labels import AUDIT_LABELS
from scheduling.domain.fhir_audit_action import audit_action_code

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
