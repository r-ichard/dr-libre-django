"""Task 23a, spec 15.6: a write body read as one command, or the FHIR path of the first refusal."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from scheduling.domain.fhir_appointment_write import (
    Book,
    ChangeStatus,
    InvalidTransition,
    Join,
    NoChange,
    Reschedule,
    decode_create,
    decode_update,
)
from scheduling.domain.fhir_slot_id import slot_id
from scheduling.domain.vocabulary import AppointmentStatus

PATIENT, PRACTITIONER, ROOM, TYPE, RULE = (UUID(int=number) for number in range(1, 6))
STARTS = datetime(2026, 3, 5, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 3, 6, 10, 0, tzinfo=UTC)
SERVICE_TYPE = [{"coding": [{"code": str(TYPE)}]}]


def _actor(resource_type: str, identifier: UUID) -> dict[str, object]:
    return {"actor": {"reference": f"{resource_type}/{identifier}"}}


def _create(**changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "resourceType": "Appointment",
        "status": "proposed",
        "serviceType": SERVICE_TYPE,
        "start": "2026-03-05T09:00:00Z",
        "participant": [_actor("Patient", PATIENT), _actor("Practitioner", PRACTITIONER)],
    }
    body.update(changes)
    return body


def returns_book_with_every_participant_and_reason_when_start_is_given() -> None:
    body = _create(
        participant=[
            _actor("Patient", PATIENT),
            _actor("Practitioner", PRACTITIONER),
            _actor("Location", ROOM),
        ],
        reasonCode=[{"text": "  Cough  "}],
    )
    assert decode_create(body) == Book(TYPE, STARTS, None, PRACTITIONER, PATIENT, ROOM, "Cough")


def returns_book_without_actors_when_no_participant_is_sent() -> None:
    body = _create()
    del body["participant"]
    assert decode_create(body) == Book(TYPE, STARTS, None, None, None, None, "")


def returns_book_with_rule_and_slot_start_when_slot_is_referenced() -> None:
    reference = f"Slot/{slot_id(RULE, TYPE, LATER)}"
    body = _create(slot=[{"reference": reference}])
    del body["start"]
    assert decode_create(body) == Book(TYPE, LATER, RULE, PRACTITIONER, PATIENT, None, "")


@pytest.mark.parametrize(
    "reference",
    [
        f"Schedule/{slot_id(RULE, TYPE, LATER)}",
        f"Slot/{slot_id(RULE, UUID(int=9), LATER)}",
        "Slot/garbage",
        "",
    ],
)
def returns_slot_path_when_slot_reference_is_not_for_this_type(reference: str) -> None:
    assert decode_create(_create(slot=[{"reference": reference}])) == "Appointment.slot"


def returns_slot_path_when_slot_item_is_not_an_object() -> None:
    assert decode_create(_create(slot=["Slot/x"])) == "Appointment.slot"


def returns_start_path_when_start_is_missing_or_has_no_zone() -> None:
    assert decode_create(_create(start="2026-03-05T09:00:00")) == "Appointment.start"
    assert decode_create(_create(start="soon")) == "Appointment.start"
    assert decode_create(_create(start=5)) == "Appointment.start"


@pytest.mark.parametrize("status", ["booked", "cancelled", "pending", None, 3])
def returns_status_path_when_create_status_is_not_proposed_or_waitlist(status: object) -> None:
    assert decode_create(_create(status=status)) == "Appointment.status"


@pytest.mark.parametrize(
    "service_type",
    [
        None,
        [],
        SERVICE_TYPE * 2,
        ["text"],
        [{"coding": []}],
        [{"coding": [{"code": str(TYPE)}, {"code": str(TYPE)}]}],
        [{"coding": ["x"]}],
        [{"coding": [{"code": "not-a-uuid"}]}],
        [{"coding": [{}]}],
    ],
)
def returns_service_type_path_when_service_type_is_not_one_coded_uuid(
    service_type: object,
) -> None:
    assert decode_create(_create(serviceType=service_type)) == "Appointment.serviceType"


@pytest.mark.parametrize(
    "participant",
    [
        [_actor("Patient", PATIENT), _actor("Patient", PATIENT)],
        [_actor("Device", PATIENT)],
        [{"actor": {"reference": "Patient/not-a-uuid"}}],
        [{"actor": {}}],
        [{}],
        ["Patient"],
    ],
)
def returns_participant_path_when_actor_is_repeated_or_unknown(participant: object) -> None:
    assert decode_create(_create(participant=participant)) == "Appointment.participant"


def _waitlist(**changes: object) -> dict[str, object]:
    body = _create(
        status="waitlist",
        requestedPeriod=[{"start": "2026-03-05T09:00:00Z", "end": "2026-03-06T10:00:00Z"}],
    )
    del body["start"]
    body.update(changes)
    return body


def returns_join_with_period_when_status_is_waitlist() -> None:
    assert decode_create(_waitlist()) == Join(TYPE, STARTS, LATER, PRACTITIONER, PATIENT)


@pytest.mark.parametrize(
    "period",
    [
        None,
        [],
        ["x"],
        [{"start": "2026-03-05T09:00:00Z"}],
        [{"end": "2026-03-06T10:00:00Z"}],
        [{"start": "2026-03-05T09:00:00", "end": "2026-03-06T10:00:00Z"}],
    ],
)
def returns_requested_period_path_when_window_is_incomplete(period: object) -> None:
    assert decode_create(_waitlist(requestedPeriod=period)) == "Appointment.requestedPeriod"


def _stored(**changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "resourceType": "Appointment",
        "id": "abc",
        "meta": {"versionId": "1"},
        "status": "booked",
        "start": "2026-03-05T09:00:00Z",
        "end": "2026-03-05T09:30:00Z",
        "serviceType": SERVICE_TYPE,
        "participant": [_actor("Patient", PATIENT)],
    }
    body.update(changes)
    return body


def _sent(**changes: object) -> dict[str, object]:
    body = _stored(meta={"versionId": "9"})
    body.update(changes)
    return body


def returns_no_change_when_body_equals_stored_apart_from_meta() -> None:
    assert decode_update(_stored(), _sent()) == NoChange()


def returns_reschedule_when_start_moves_and_end_keeps_duration() -> None:
    body = _sent(start="2026-03-06T10:00:00Z", end="2026-03-06T10:30:00Z")
    assert decode_update(_stored(), body) == Reschedule(LATER)


def returns_end_path_when_end_is_not_start_plus_stored_duration() -> None:
    body = _sent(start="2026-03-06T10:00:00Z", end="2026-03-06T10:31:00Z")
    assert decode_update(_stored(), body) == "Appointment.end"
    assert decode_update(_stored(), _sent(end="2026-03-05T09:29:00Z")) == "Appointment.end"


def returns_end_path_when_end_is_missing() -> None:
    body = _sent()
    del body["end"]
    assert decode_update(_stored(), body) == "Appointment.end"


def returns_start_path_when_start_is_missing_or_naive() -> None:
    body = _sent()
    del body["start"]
    assert decode_update(_stored(), body) == "Appointment.start"
    assert decode_update(_stored(), _sent(start="2026-03-05T09:00:00")) == "Appointment.start"


def returns_start_path_when_stored_resource_has_no_start() -> None:
    stored = _stored()
    del stored["start"]
    assert decode_update(stored, _sent()) == "Appointment.start"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("participant", [_actor("Patient", UUID(int=77))]),
        ("serviceType", [{"coding": [{"code": str(UUID(int=77))}]}]),
        ("slot", [{"reference": "Slot/x"}]),
        ("comment", "note"),
        ("id", "other"),
    ],
)
def returns_element_path_when_a_fixed_element_changes(name: str, value: object) -> None:
    assert decode_update(_stored(), _sent(**{name: value})) == f"Appointment.{name}"


def returns_element_path_when_a_stored_element_is_dropped() -> None:
    body = _sent()
    del body["participant"]
    assert decode_update(_stored(), body) == "Appointment.participant"


def returns_first_sorted_element_path_when_two_elements_change() -> None:
    body = _sent(participant=[], comment="x")
    assert decode_update(_stored(), body) == "Appointment.comment"


def returns_change_status_with_reason_when_cancelled_with_reason() -> None:
    body = _sent(status="cancelled", cancelationReason={"text": " Moved "})
    assert decode_update(_stored(), body) == ChangeStatus(AppointmentStatus.CANCELLED, "Moved")


@pytest.mark.parametrize("reason", [None, {"text": "  "}, {}, "text"])
def returns_cancelation_reason_path_when_cancelled_without_reason(reason: object) -> None:
    body = _sent(status="cancelled", cancelationReason=reason)
    assert decode_update(_stored(), body) == "Appointment.cancelationReason"


@pytest.mark.parametrize(
    ("fhir", "internal"),
    [
        ("checked-in", AppointmentStatus.CHECKED_IN),
        ("fulfilled", AppointmentStatus.COMPLETED),
        ("noshow", AppointmentStatus.NO_SHOW),
    ],
)
def returns_change_status_when_status_is_a_staff_transition(
    fhir: str, internal: AppointmentStatus
) -> None:
    assert decode_update(_stored(), _sent(status=fhir)) == ChangeStatus(internal, "")


@pytest.mark.parametrize("status", ["proposed", "pending", "booked", "arrived", "waitlist"])
def returns_invalid_transition_when_status_is_known_but_not_a_target(status: str) -> None:
    stored = _stored(status="checked-in")
    assert decode_update(stored, _sent(status=status)) == InvalidTransition()


@pytest.mark.parametrize("status", ["bogus", None, 4])
def returns_status_path_when_status_is_not_a_fhir_status(status: object) -> None:
    assert decode_update(_stored(), _sent(status=status)) == "Appointment.status"


def returns_status_path_when_start_and_status_both_change() -> None:
    body = _sent(start="2026-03-06T10:00:00Z", end="2026-03-06T10:30:00Z", status="noshow")
    assert decode_update(_stored(), body) == "Appointment.status"


def returns_cancelation_reason_path_when_reason_changes_without_status() -> None:
    body = _sent(cancelationReason={"text": "late edit"})
    assert decode_update(_stored(), body) == "Appointment.cancelationReason"


def returns_no_change_when_a_cancelled_appointment_is_sent_back_with_its_reason() -> None:
    reason = {"text": "Moved"}
    stored = _stored(status="cancelled", cancelationReason=reason)
    assert decode_update(stored, _sent(status="cancelled", cancelationReason=reason)) == NoChange()


@pytest.mark.parametrize("slot", ["abc", {"reference": "Slot/x"}, []])
def returns_book_by_start_when_slot_is_not_a_non_empty_list(slot: object) -> None:
    assert decode_create(_create(slot=slot)) == Book(
        TYPE, STARTS, None, PRACTITIONER, PATIENT, None, ""
    )


@pytest.mark.parametrize("reason", ["abc", {"text": "x"}, [], [{}], ["x"]])
def returns_empty_reason_when_reason_code_is_not_a_list_with_text(reason: object) -> None:
    assert isinstance(decode_create(_create(reasonCode=reason)), Book)
    assert decode_create(_create(reasonCode=reason)).reason == ""  # type: ignore[union-attr]


def returns_room_when_slot_and_location_are_both_sent() -> None:
    reference = f"Slot/{slot_id(RULE, TYPE, LATER)}"
    body = _create(
        slot=[{"reference": reference}],
        participant=[_actor("Patient", PATIENT), _actor("Location", ROOM)],
    )
    assert decode_create(body) == Book(TYPE, LATER, RULE, None, PATIENT, ROOM, "")
