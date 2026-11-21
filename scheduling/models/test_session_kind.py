"""Task 05: how a session was opened is a closed list of kinds."""

import pytest

from scheduling.models.builders import make, refuses

pytestmark = pytest.mark.django_db


def returns_row_when_session_is_opened_by_a_known_kind() -> None:
    for kind in ["PASSWORD", "EMAIL_LINK", "BOOKING_CODE"]:
        assert make("Session", opened_by=kind).pk is not None


def returns_refusal_when_session_is_opened_by_an_unknown_kind() -> None:
    refuses("Session", opened_by="MAGIC")
