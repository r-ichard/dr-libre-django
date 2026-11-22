"""Task 25b: no notification or email a person reads holds an ISO date."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from scheduling.domain import placement_rules
from scheduling.domain.email_content import (
    EmailSubject,
    patient_email,
    sign_in_link_email,
    verification_code_email,
)

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
MOMENT = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
BERLIN = ZoneInfo("Europe/Berlin")


@pytest.mark.parametrize(
    "text_of",
    [
        placement_rules.booked_notification_text,
        placement_rules.cancelled_notification_text,
        placement_rules.rescheduled_notification_text,
    ],
)
def returns_text_without_iso_date_when_notification_text_is_built(text_of: object) -> None:
    text = text_of(MOMENT, BERLIN)  # type: ignore[operator]

    assert ISO_DATE.search(text) is None
    assert "Monday 23 November 2026, 13:00 (Europe/Berlin)" in text


def returns_email_bodies_without_iso_date_when_every_email_is_built() -> None:
    bodies = [
        patient_email(EmailSubject("Booked", "http://x.test", MOMENT, BERLIN)).body,
        verification_code_email("123456", 10).body,
        sign_in_link_email("http://x.test/l", 15).body,
    ]

    assert [ISO_DATE.search(body) for body in bodies] == [None, None, None]
