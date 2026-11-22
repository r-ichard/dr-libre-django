from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from scheduling.domain.failure import Failure, FieldMessage
from scheduling.views.pages.local_time import errors_by_field, utc_from_local

BERLIN = ZoneInfo("Europe/Berlin")


def returns_utc_when_wall_time_is_plain() -> None:
    assert utc_from_local("2030-01-07T10:00", BERLIN) == datetime(2030, 1, 7, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "raw",
    ["", "tomorrow", "2030-03-31T02:30", "2026-03-29T02:30", "2030-01-07T10:00+01:00"],
)
def returns_nothing_when_time_is_missing_skipped_or_has_offset(raw: str) -> None:
    assert utc_from_local(raw, BERLIN) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2030-10-27T02:30", datetime(2030, 10, 27, 0, 30, tzinfo=UTC)),
        ("2026-10-25T02:00", datetime(2026, 10, 25, 0, 0, tzinfo=UTC)),
        ("2026-10-25T02:59", datetime(2026, 10, 25, 0, 59, tzinfo=UTC)),
        ("2026-10-25T03:00", datetime(2026, 10, 25, 2, 0, tzinfo=UTC)),
    ],
)
def returns_first_occurrence_when_wall_time_happens_twice(raw: str, expected: datetime) -> None:
    assert utc_from_local(raw, BERLIN) == expected


def returns_first_message_of_each_field() -> None:
    failure = Failure.invalid_input([FieldMessage("room", "one"), FieldMessage("room", "two")])

    assert errors_by_field(failure) == {"room": "one"}
