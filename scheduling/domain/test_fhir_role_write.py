"""Task 24c: the PractitionerRole write body read as profile fields and time off changes. The
expected values restate spec 15.2 and 15.4, not the code."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from scheduling.domain.fhir_common import CANONICAL_BASE, SPECIALTY_SYSTEM, Resource
from scheduling.domain.fhir_role_write import (
    ADMIN_FREE,
    CREATE_FREE,
    OWN_FREE,
    TimeOffAddition,
    TimeOffChanges,
    role_difference,
    role_values,
    time_off_changes,
)

USER = "0190c5a0-0000-7000-8000-000000000001"
DEPARTMENT = "0190c5a0-0000-7000-8000-000000000002"
ROOM = "0190c5a0-0000-7000-8000-000000000003"
ENTRY = "0190c5a0-0000-7000-8000-000000000004"
OTHER_ENTRY = "0190c5a0-0000-7000-8000-000000000005"
START = datetime(2030, 1, 1, 9, tzinfo=UTC)
END = START + timedelta(hours=8)


def _extension(name: str, **value: object) -> Resource:
    return {"url": f"{CANONICAL_BASE}/StructureDefinition/{name}", **value}


def _body() -> Resource:
    return {
        "resourceType": "PractitionerRole",
        "practitioner": {"reference": f"Practitioner/{USER}"},
        "organization": {"reference": f"Organization/{DEPARTMENT}"},
        "specialty": [{"coding": [{"system": SPECIALTY_SYSTEM, "code": "cardiology"}]}],
        "location": [{"reference": f"Location/{ROOM}"}],
        "extension": [
            _extension("role-bio", valueString="Heart rhythm."),
            _extension("role-round-robin-weight", valueInteger=3),
        ],
    }


def _period(start: datetime = START, end: datetime = END, **more: object) -> Resource:
    return {"during": {"start": start.isoformat(), "end": end.isoformat()}, **more}


def returns_every_profile_field_when_the_body_is_complete() -> None:
    assert role_values(_body()) == {
        "user_id": UUID(USER),
        "department_id": UUID(DEPARTMENT),
        "specialty_code": "cardiology",
        "default_room_id": UUID(ROOM),
        "bio": "Heart rhythm.",
        "round_robin_weight": 3,
    }


def returns_no_room_and_an_empty_bio_and_no_weight_when_the_body_leaves_them_out() -> None:
    body = _body()
    del body["location"], body["extension"]

    values = role_values(body)

    assert values == {
        "user_id": UUID(USER),
        "department_id": UUID(DEPARTMENT),
        "specialty_code": "cardiology",
        "default_room_id": None,
        "bio": "",
    }


def returns_the_element_name_when_a_required_reference_or_the_specialty_is_bad() -> None:
    for element, bad in (
        ("practitioner", {"reference": f"Organization/{USER}"}),
        ("organization", {"reference": "Organization/not-an-id"}),
        ("specialty", []),
        ("location", [{"reference": f"Practitioner/{ROOM}"}]),
    ):
        body = _body()
        body[element] = bad

        assert role_values(body) == f"PractitionerRole.{element}"


def returns_empty_when_the_body_repeats_the_stored_role_and_changes_only_free_elements() -> None:
    stored: Resource = {**_body(), "active": True, "availableTime": [{"daysOfWeek": ["mon"]}]}
    body: Resource = {**stored, "extension": [], "specialty": [], "location": []}

    assert role_difference(body, stored, ADMIN_FREE) == ""


def returns_the_element_when_a_derived_element_differs() -> None:
    stored: Resource = {**_body(), "active": True, "availableTime": [{"daysOfWeek": ["mon"]}]}

    assert role_difference({**stored, "active": False}, stored, ADMIN_FREE) == (
        "PractitionerRole.active"
    )
    assert role_difference({**stored, "availableTime": []}, stored, ADMIN_FREE) == (
        "PractitionerRole.availableTime"
    )
    assert role_difference({**stored, "notAvailable": [_period()]}, stored, CREATE_FREE) == (
        "PractitionerRole.notAvailable"
    )
    assert role_difference({**stored, "notAvailable": [_period()]}, stored, OWN_FREE) == ""
    assert role_difference({**stored, "notAvailable": [_period()]}, stored, ADMIN_FREE) == ""
    assert role_difference({**stored, "organization": {}}, stored, OWN_FREE) == (
        "PractitionerRole.organization"
    )
    assert role_difference({**stored, "practitioner": {}}, stored, ADMIN_FREE) == (
        "PractitionerRole.practitioner"
    )


def returns_the_first_in_element_order_when_two_elements_differ() -> None:
    stored: Resource = {"extension": [{"url": "a"}], "active": True}

    assert role_difference({"extension": [{"url": "b"}], "active": False}, stored, OWN_FREE) == (
        "PractitionerRole.extension"
    )


def returns_nothing_changed_when_a_client_leaves_out_an_empty_array() -> None:
    assert role_difference({}, {"availableTime": [], "notAvailable": []}, OWN_FREE) == ""
    assert role_difference({"availableTime": []}, {}, OWN_FREE) == ""


def returns_an_addition_when_an_entry_has_no_id() -> None:
    changes = time_off_changes({"notAvailable": [_period(description="Congress")]}, {})

    assert changes == TimeOffChanges((TimeOffAddition(START, END, "Congress"),), ())
    assert not isinstance(changes, str)
    assert not changes.is_empty


def returns_an_empty_reason_when_a_new_entry_has_no_description() -> None:
    changes = time_off_changes({"notAvailable": [_period()]}, {})

    assert changes == TimeOffChanges((TimeOffAddition(START, END, ""),), ())


def returns_a_removal_when_a_stored_entry_is_left_out() -> None:
    stored: Resource = {
        "notAvailable": [{"id": OTHER_ENTRY, **_period()}, {"id": ENTRY, **_period()}]
    }

    changes = time_off_changes({}, stored)

    assert changes == TimeOffChanges((), tuple(sorted((ENTRY, OTHER_ENTRY))))
    assert isinstance(changes, TimeOffChanges)
    assert not changes.is_empty


def returns_no_changes_when_stored_entries_are_repeated_unchanged() -> None:
    stored: Resource = {"notAvailable": [{"id": ENTRY, **_period(description="Congress")}]}

    changes = time_off_changes(stored, stored)

    assert changes == TimeOffChanges((), ())
    assert isinstance(changes, TimeOffChanges)
    assert changes.is_empty


def returns_no_changes_when_a_stored_default_description_is_repeated_or_left_out() -> None:
    stored: Resource = {"notAvailable": [{"id": ENTRY, **_period(description="Time off")}]}
    bare: Resource = {"notAvailable": [{"id": ENTRY, **_period()}]}
    spaced: Resource = {"notAvailable": [{"id": ENTRY, **_period(description="  ")}]}

    assert time_off_changes(bare, stored) == TimeOffChanges((), ())
    assert time_off_changes(spaced, stored) == TimeOffChanges((), ())


def returns_the_entry_position_when_a_stored_entry_is_edited() -> None:
    stored: Resource = {"notAvailable": [{"id": ENTRY, **_period(description="Congress")}]}
    edits = (
        _period(START, END + timedelta(hours=1), description="Congress"),
        _period(START + timedelta(hours=1), END, description="Congress"),
        _period(description="Holiday"),
    )

    for edit in edits:
        body: Resource = {"notAvailable": [{"id": ENTRY, **edit}]}

        assert time_off_changes(body, stored) == "PractitionerRole.notAvailable[0]"


def returns_the_entry_position_when_an_id_is_unknown_repeated_or_not_text() -> None:
    stored: Resource = {"notAvailable": [{"id": ENTRY, **_period()}]}
    kept: Resource = {"id": ENTRY, **_period()}
    entries = (
        [{"id": OTHER_ENTRY, **_period()}],
        [kept, kept],
        [{"id": 7, **_period()}],
    )

    results = [time_off_changes({"notAvailable": entry}, stored) for entry in entries]

    assert results == [
        "PractitionerRole.notAvailable[0]",
        "PractitionerRole.notAvailable[1]",
        "PractitionerRole.notAvailable[0]",
    ]


def returns_the_entry_position_when_a_new_period_is_unreadable() -> None:
    bad_periods: tuple[object, ...] = (
        None,
        "2030-01-01",
        {},
        {"start": "not a date", "end": END.isoformat()},
        {"start": START.isoformat(), "end": "not a date"},
        {"start": "2030-01-01T09:00:00", "end": END.isoformat()},
        {"start": START.isoformat(), "end": "2030-01-01T17:00:00"},
    )

    for bad in bad_periods:
        body: Resource = {"notAvailable": [_period(), {"during": bad}]}

        assert time_off_changes(body, {}) == "PractitionerRole.notAvailable[1]"


def returns_no_changes_when_not_available_is_missing_or_holds_no_objects() -> None:
    bodies: tuple[Resource, ...] = ({}, {"notAvailable": "x"}, {"notAvailable": ["x", 3]})
    for body in bodies:
        assert time_off_changes(body, {}) == TimeOffChanges((), ())


def returns_no_room_when_the_location_is_an_empty_list_or_not_a_list() -> None:
    locations: tuple[object, ...] = ([], "Location/x")
    for location in locations:
        body = _body()
        body["location"] = location

        values = role_values(body)

        assert isinstance(values, dict)
        assert values["default_room_id"] is None
