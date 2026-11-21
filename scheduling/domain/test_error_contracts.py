"""Mutation-proof tests: the exact failure codes and error messages callers and logs rely on."""

import os
import time as time_module
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from scheduling.domain.audit_metadata import AuditMetadata, email_domain, field_name
from scheduling.domain.booking_rules import BookingAction, BookingAttempt, violated_rules
from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.free_slots import AvailabilityWindow, SlotType, TimeRange, free_slots
from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import Role


@pytest.mark.parametrize(
    ("build", "code"),
    [
        (Failure.unauthenticated, FailureCode.UNAUTHENTICATED),
        (Failure.forbidden, FailureCode.FORBIDDEN),
        (Failure.not_found, FailureCode.NOT_FOUND),
        (Failure.no_room_available, FailureCode.NO_ROOM_AVAILABLE),
        (Failure.no_clinician_available, FailureCode.NO_CLINICIAN_AVAILABLE),
        (lambda: Failure.has_dependents(["room"]), FailureCode.HAS_DEPENDENTS),
        (lambda: Failure.rule_violation(["lead_time"]), FailureCode.RULE_VIOLATION),
    ],
)
def returns_matching_code_when_failure_constructor_is_called(
    build: Callable[[], Failure], code: FailureCode
) -> None:
    assert build().code is code


def _expect_message(build: Callable[[], object], message: str) -> None:
    with pytest.raises(ValueError) as caught:
        build()
    assert str(caught.value) == message


def returns_exact_message_when_audit_metadata_rejects_a_value() -> None:
    _expect_message(
        lambda: field_name("Jane Doe"), "a field name is lower case letters and underscores only"
    )
    _expect_message(
        lambda: email_domain("Jane Doe"), "an email domain is a host name taken from an address"
    )
    _expect_message(
        lambda: AuditMetadata(email_domain="Jane Doe"),  # type: ignore[arg-type]
        "an email domain is a host name taken from an address",
    )
    _expect_message(
        lambda: AuditMetadata(ids={"patient_id": "x"}),  # type: ignore[dict-item]
        "an id is a UUID or an integer",
    )
    _expect_message(
        lambda: AuditMetadata(counts={"row_count": "x"}),  # type: ignore[dict-item]
        "a count is an integer",
    )
    _expect_message(
        lambda: AuditMetadata(statuses={"new_status": "x"}),  # type: ignore[dict-item]
        "a status is a member of a StrEnum",
    )
    _expect_message(
        lambda: AuditMetadata(counts={"note": 1}),
        "key must name its kind and end with one of ('_count',)",
    )


def returns_integer_id_when_metadata_ids_hold_an_integer() -> None:
    assert AuditMetadata(ids={"patient_id": 7}).to_json()["ids"] == {"patient_id": "7"}


def raises_exact_message_when_request_context_instant_is_naive() -> None:
    _expect_message(
        lambda: RequestContext(correlation_id="abc", now=datetime(2026, 1, 1)),  # noqa: DTZ001
        "RequestContext.now must be timezone aware",
    )


def raises_exact_message_when_booking_attempt_lacks_a_start() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    def attempt(
        action: BookingAction, new_start: datetime | None, current: datetime | None
    ) -> None:  # noqa: E501
        violated_rules(BookingAttempt(action, Role.PATIENT, now, new_start, current, 0, True, True))

    _expect_message(
        lambda: attempt(BookingAction.BOOK, None, None),
        "new_start is required to book or reschedule",
    )
    _expect_message(
        lambda: attempt(BookingAction.CANCEL, None, None),
        "current_start is required to reschedule or cancel",
    )


@pytest.fixture
def new_york_system_clock() -> Iterator[None]:
    original = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    time_module.tzset()
    yield
    if original is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = original
    time_module.tzset()


def returns_utc_slots_when_the_system_clock_zone_is_not_utc(new_york_system_clock: None) -> None:
    zone = ZoneInfo("Europe/Paris")
    rule = AvailabilityWindow(1, time(9), time(10), timedelta(hours=1), date(2020, 1, 1), None)
    window = TimeRange(datetime(2026, 1, 4, tzinfo=UTC), datetime(2026, 1, 6, tzinfo=UTC))
    slot_type = SlotType(duration=timedelta(hours=1), buffer=timedelta(0))

    offered = free_slots([rule], slot_type, [], [], window, datetime(2020, 1, 1, tzinfo=UTC), zone)

    assert offered == [datetime(2026, 1, 5, 8, tzinfo=UTC)]
    assert [slot.utcoffset() for slot in offered] == [timedelta(0)]
    assert [slot.tzinfo for slot in offered] == [UTC]
