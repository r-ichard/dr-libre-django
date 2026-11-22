"""Task 18 and 17c: every audit action an admin record write can produce has plain words."""

import pytest

from scheduling.domain.audit_labels import audit_label

RECORDS = {
    "hospital": "Hospital",
    "specialty": "Specialty",
    "department": "Department",
    "room": "Room",
    "appointment_type": "Appointment type",
}
VERBS = {"create": "created", "update": "updated", "delete": "deleted"}


@pytest.mark.parametrize("record", sorted(RECORDS))
@pytest.mark.parametrize("verb", sorted(VERBS))
def returns_plain_words_when_admin_record_action_is_labelled(record: str, verb: str) -> None:
    assert audit_label(f"{record}.{verb}") == f"{RECORDS[record]} {VERBS[verb]}"
