"""Section 10: every audit action an admin record write can produce has plain words."""

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


@pytest.mark.parametrize(
    ("action", "words"),
    [
        ("user.create", "User created"),
        ("user.update", "User updated"),
        ("user.deactivate", "User deactivated"),
        ("user.activate", "User activated"),
        ("user.delete", "User deleted"),
        ("clinician.create", "Clinician profile created"),
        ("clinician.update", "Clinician profile updated"),
        ("clinician.delete", "Clinician profile deleted"),
    ],
)
def returns_plain_words_when_user_and_clinician_actions_are_labelled(
    action: str, words: str
) -> None:
    assert audit_label(action) == words
