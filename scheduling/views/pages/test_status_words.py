"""Task 25d, item 2: every status value of the domain vocabulary has one kind and one word in
one table, so no screen shows a status by colour alone."""

from __future__ import annotations

import pytest

from scheduling.domain.vocabulary import AppointmentStatus, WaitlistStatus
from scheduling.views.pages import status_words


@pytest.mark.parametrize("status", list(AppointmentStatus))
def returns_a_kind_and_a_word_when_an_appointment_status_is_looked_up(
    status: AppointmentStatus,
) -> None:
    kind, word = status_words.APPOINTMENT_BADGES[status]

    assert kind in status_words.BADGE_KINDS
    assert word.strip()


@pytest.mark.parametrize("status", list(WaitlistStatus))
def returns_a_kind_and_a_word_when_a_waitlist_status_is_looked_up(status: WaitlistStatus) -> None:
    kind, word = status_words.WAITLIST_BADGES[status]

    assert kind in status_words.BADGE_KINDS
    assert word.strip()


def returns_a_word_for_each_active_state_of_a_record() -> None:
    assert status_words.ACTIVE_BADGE == ("success", "Active")
    assert status_words.INACTIVE_BADGE == ("pending", "Inactive")
