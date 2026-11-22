"""Task 23a, spec 15.3: the three origins of an `Appointment`, stated as exact bodies."""

import time
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from scheduling.domain.fhir_appointment import (
    BookingFacts,
    HoldFacts,
    ServiceFacts,
    WaitlistFacts,
    booking_resource,
    hold_resource,
    waitlist_resource,
)
from scheduling.domain.vocabulary import AppointmentStatus, WaitlistStatus

FIRST, SECOND, THIRD, FOURTH, FIFTH = (UUID(int=number) for number in range(1, 6))
BASE = "https://drlibre.example/fhir"
MOMENT = datetime(2026, 3, 4, 5, 6, 7, 891000, tzinfo=UTC)
STARTS = datetime(2026, 3, 5, 9, 0, tzinfo=UTC)
ENDS = datetime(2026, 3, 5, 9, 30, tzinfo=UTC)
SERVICE = ServiceFacts(type_id=SECOND, type_name="Checkup")
META = {"versionId": "7", "lastUpdated": "2026-03-04T05:06:07.891Z"}
SERVICE_TYPE = [
    {
        "coding": [
            {"system": f"{BASE}/CodeSystem/service-type", "code": str(SECOND), "display": "Checkup"}
        ]
    }
]


def _extension(name: str, value: str) -> dict[str, str]:
    return {"url": f"{BASE}/StructureDefinition/{name}", "valueCode": value}


def _actor(resource_type: str, identifier: UUID) -> dict[str, object]:
    return {"actor": {"reference": f"{resource_type}/{identifier}"}, "status": "accepted"}


def _booking(**changes: object) -> BookingFacts:
    fields: dict[str, object] = {
        "id": FIRST,
        "version": 7,
        "updated_at": MOMENT,
        "status": "BOOKED",
        "source": "ONLINE",
        "starts_at": STARTS,
        "ends_at": ENDS,
        "service": SERVICE,
        "patient_id": THIRD,
        "practitioner_id": FOURTH,
        "room_id": FIFTH,
        "reason": "",
        "cancellation_reason": "",
        "comment": None,
    }
    fields.update(changes)
    return BookingFacts(**fields)  # type: ignore[arg-type]


def returns_exact_body_when_booking_has_room_and_reason() -> None:
    body = booking_resource(_booking(reason="Cough", source="ROUND_ROBIN"))
    assert body == {
        "resourceType": "Appointment",
        "id": str(FIRST),
        "meta": META,
        "serviceType": SERVICE_TYPE,
        "status": "booked",
        "start": "2026-03-05T09:00:00Z",
        "end": "2026-03-05T09:30:00Z",
        "participant": [
            _actor("Patient", THIRD),
            _actor("Practitioner", FOURTH),
            _actor("Location", FIFTH),
        ],
        "extension": [
            _extension("appointment-source", "round_robin"),
            _extension("appointment-status", "booked"),
        ],
        "reasonCode": [{"text": "Cough"}],
    }


def returns_no_location_reason_comment_or_cancellation_when_they_are_empty() -> None:
    body = booking_resource(_booking(room_id=None))
    assert body["participant"] == [_actor("Patient", THIRD), _actor("Practitioner", FOURTH)]
    for absent in ("reasonCode", "cancelationReason", "comment"):
        assert absent not in body


@pytest.mark.parametrize(
    ("internal", "fhir", "keeps_internal"),
    [
        (AppointmentStatus.BOOKED, "booked", True),
        (AppointmentStatus.CONFIRMED, "booked", True),
        (AppointmentStatus.CHECKED_IN, "checked-in", False),
        (AppointmentStatus.COMPLETED, "fulfilled", False),
        (AppointmentStatus.CANCELLED, "cancelled", False),
        (AppointmentStatus.NO_SHOW, "noshow", False),
    ],
)
def returns_fhir_status_and_internal_extension_only_where_two_map_to_one(
    internal: AppointmentStatus, fhir: str, keeps_internal: bool
) -> None:
    body = booking_resource(_booking(status=internal.value))
    assert body["status"] == fhir
    internal_extension = _extension("appointment-status", internal.value.lower())
    assert (internal_extension in body["extension"]) is keeps_internal  # type: ignore[operator]


def returns_cancelation_reason_and_comment_when_present() -> None:
    body = booking_resource(
        _booking(status="CANCELLED", cancellation_reason="Moved away", comment="note")
    )
    assert body["cancelationReason"] == {"text": "Moved away"}
    assert body["comment"] == "note"


def returns_utc_instants_when_the_machine_zone_is_not_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    time.tzset()
    try:
        body = booking_resource(_booking())
    finally:
        monkeypatch.undo()
        time.tzset()
    assert (body["start"], body["end"]) == ("2026-03-05T09:00:00Z", "2026-03-05T09:30:00Z")


def returns_utc_instants_when_times_carry_another_offset() -> None:
    zone = timezone(timedelta(hours=2))
    body = booking_resource(
        _booking(starts_at=STARTS.astimezone(zone), ends_at=ENDS.astimezone(zone))
    )
    assert (body["start"], body["end"]) == ("2026-03-05T09:00:00Z", "2026-03-05T09:30:00Z")


def _waitlist(**changes: object) -> WaitlistFacts:
    fields: dict[str, object] = {
        "id": FIRST,
        "version": 7,
        "updated_at": MOMENT,
        "status": "WAITING",
        "service": SERVICE,
        "patient_id": THIRD,
        "earliest_at": STARTS,
        "latest_at": ENDS,
        "preferred_practitioner_id": None,
        "offered_starts_at": None,
        "offered_ends_at": None,
        "offered_practitioner_id": None,
    }
    fields.update(changes)
    return WaitlistFacts(**fields)  # type: ignore[arg-type]


def returns_exact_waitlist_body_when_entry_is_waiting_with_preferred_clinician() -> None:
    body = waitlist_resource(_waitlist(preferred_practitioner_id=FOURTH))
    assert body == {
        "resourceType": "Appointment",
        "id": str(FIRST),
        "meta": META,
        "serviceType": SERVICE_TYPE,
        "status": "waitlist",
        "participant": [_actor("Patient", THIRD), _actor("Practitioner", FOURTH)],
        "requestedPeriod": [{"start": "2026-03-05T09:00:00Z", "end": "2026-03-05T09:30:00Z"}],
    }


def returns_offer_and_offered_clinician_when_entry_is_offered() -> None:
    body = waitlist_resource(
        _waitlist(
            status="OFFERED",
            preferred_practitioner_id=FOURTH,
            offered_practitioner_id=FIFTH,
            offered_starts_at=STARTS,
            offered_ends_at=ENDS,
        )
    )
    assert body["status"] == "proposed"
    assert (body["start"], body["end"]) == ("2026-03-05T09:00:00Z", "2026-03-05T09:30:00Z")
    assert body["participant"] == [_actor("Patient", THIRD), _actor("Practitioner", FIFTH)]


def returns_no_start_or_end_when_only_one_offered_time_is_known() -> None:
    body = waitlist_resource(_waitlist(offered_starts_at=STARTS))
    assert "start" not in body
    assert "end" not in body
    assert "participant" in body and len(body["participant"]) == 1  # type: ignore[arg-type]


def returns_cancelled_when_entry_expired() -> None:
    assert (
        waitlist_resource(_waitlist(status=WaitlistStatus.EXPIRED.value))["status"] == "cancelled"
    )


def returns_exact_hold_body_as_pending_for_staff() -> None:
    body = hold_resource(
        HoldFacts(
            id=FIRST,
            version=7,
            updated_at=MOMENT,
            source="ONLINE",
            starts_at=STARTS,
            ends_at=ENDS,
            service=SERVICE,
            practitioner_id=FOURTH,
        )
    )
    assert body == {
        "resourceType": "Appointment",
        "id": str(FIRST),
        "meta": META,
        "serviceType": SERVICE_TYPE,
        "status": "pending",
        "start": "2026-03-05T09:00:00Z",
        "end": "2026-03-05T09:30:00Z",
        "participant": [_actor("Practitioner", FOURTH)],
        "extension": [_extension("appointment-source", "online")],
    }
