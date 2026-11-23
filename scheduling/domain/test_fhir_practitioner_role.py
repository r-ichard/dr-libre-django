"""Section 15.2: a clinician profile as a PractitionerRole; expected values from FHIR R4
`PractitionerRole.notAvailable`: `description` and `during`, a Period with start and end."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_practitioner_role import (
    RoleSource,
    TimeOffSource,
    practitioner_role,
)

MOMENT = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


def _a_role(time_off: tuple[TimeOffSource, ...]) -> RoleSource:
    return RoleSource(
        id=uuid4(),
        practitioner_id=uuid4(),
        department_id=uuid4(),
        specialty_code="cardiology",
        specialty_name="Cardiology",
        default_room_id=None,
        bio="",
        round_robin_weight=1,
        version=1,
        updated_at=MOMENT,
        is_active=True,
        service_ids=(),
        rules=(),
        time_off=time_off,
    )


def _entries(source: RoleSource) -> list[Resource]:
    entries = practitioner_role(source)["notAvailable"]
    assert isinstance(entries, list)
    return entries


def returns_not_available_with_id_description_and_during_when_time_off_exists() -> None:
    period_id = UUID("11111111-1111-1111-1111-111111111111")
    item = TimeOffSource(
        id=period_id,
        starts_at=datetime(2026, 3, 2, 8, 0, tzinfo=UTC),
        ends_at=datetime(2026, 3, 3, 17, 30, tzinfo=UTC),
        reason="Dentist",
    )

    assert _entries(_a_role((item,))) == [
        {
            "id": str(period_id),
            "description": "Dentist",
            "during": {"start": "2026-03-02T08:00:00.000Z", "end": "2026-03-03T17:30:00.000Z"},
        }
    ]


def returns_the_default_description_when_the_reason_is_empty() -> None:
    item = TimeOffSource(uuid4(), MOMENT, MOMENT.replace(hour=10), "")

    entry = _entries(_a_role((item,)))[0]

    assert entry["description"] == "Time off"
    assert "period" not in entry


def returns_no_not_available_when_there_is_no_time_off() -> None:
    assert "notAvailable" not in practitioner_role(_a_role(()))


def returns_one_entry_per_time_off_in_the_given_order() -> None:
    first = TimeOffSource(uuid4(), MOMENT, MOMENT.replace(hour=10), "a")
    second = TimeOffSource(uuid4(), MOMENT.replace(day=2), MOMENT.replace(day=3), "b")

    entries = _entries(_a_role((first, second)))

    assert [entry["description"] for entry in entries] == ["a", "b"]
