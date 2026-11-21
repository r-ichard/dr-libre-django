"""Sections 5.2 step 5, 5.4 and 11: who may book for whom, which room, the notification text."""

from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from scheduling.domain.failure import Failure, FieldMessage, Success
from scheduling.domain.placement_rules import (
    BookingActor,
    BookingParties,
    NamedParties,
    authorize_booking,
    booked_notification_text,
    choose_room,
)
from scheduling.domain.vocabulary import AppointmentSource, Role

PATIENT_ID = uuid4()
OTHER_PATIENT_ID = uuid4()
CLINICIAN_ID = uuid4()
OTHER_CLINICIAN_ID = uuid4()
ROOM_ID = uuid4()
FIRST_ROOM_ID = UUID(int=1)
SECOND_ROOM_ID = UUID(int=2)
DEFAULT_ROOM_ID = UUID(int=3)


def _patient() -> BookingActor:
    return BookingActor(Role.PATIENT, PATIENT_ID, None)


def _clinician() -> BookingActor:
    return BookingActor(Role.CLINICIAN, uuid4(), CLINICIAN_ID)


def _admin() -> BookingActor:
    return BookingActor(Role.ADMIN, uuid4(), None)


def returns_forbidden_when_patient_names_a_patient() -> None:
    named = NamedParties(patient_id=OTHER_PATIENT_ID, clinician_id=None, room_id=None)

    assert authorize_booking(_patient(), named) == Failure.forbidden()


def returns_forbidden_when_patient_names_a_room() -> None:
    named = NamedParties(patient_id=None, clinician_id=CLINICIAN_ID, room_id=ROOM_ID)

    assert authorize_booking(_patient(), named) == Failure.forbidden()


def returns_online_booking_for_the_patient_when_patient_names_a_clinician() -> None:
    named = NamedParties(patient_id=None, clinician_id=CLINICIAN_ID, room_id=None)

    expected = BookingParties(PATIENT_ID, CLINICIAN_ID, None, AppointmentSource.ONLINE)
    assert authorize_booking(_patient(), named) == Success(expected)


def returns_round_robin_booking_when_patient_names_no_clinician() -> None:
    named = NamedParties(patient_id=None, clinician_id=None, room_id=None)

    expected = BookingParties(PATIENT_ID, None, None, AppointmentSource.ROUND_ROBIN)
    assert authorize_booking(_patient(), named) == Success(expected)


def returns_forbidden_when_clinician_names_another_clinician() -> None:
    named = NamedParties(patient_id=PATIENT_ID, clinician_id=OTHER_CLINICIAN_ID, room_id=None)

    assert authorize_booking(_clinician(), named) == Failure.forbidden()


def returns_own_calendar_when_clinician_names_nobody() -> None:
    named = NamedParties(patient_id=PATIENT_ID, clinician_id=None, room_id=None)

    expected = BookingParties(PATIENT_ID, CLINICIAN_ID, None, AppointmentSource.STAFF)
    assert authorize_booking(_clinician(), named) == Success(expected)


def returns_invalid_input_when_clinician_names_no_patient() -> None:
    named = NamedParties(patient_id=None, clinician_id=None, room_id=None)

    expected = Failure.invalid_input([FieldMessage("patient_id", "A patient is required.")])
    assert authorize_booking(_clinician(), named) == expected


def returns_invalid_input_when_admin_names_no_clinician() -> None:
    named = NamedParties(patient_id=PATIENT_ID, clinician_id=None, room_id=None)

    expected = Failure.invalid_input([FieldMessage("clinician_id", "A clinician is required.")])
    assert authorize_booking(_admin(), named) == expected


def returns_named_room_when_staff_names_one() -> None:
    named = NamedParties(patient_id=PATIENT_ID, clinician_id=CLINICIAN_ID, room_id=ROOM_ID)

    expected = BookingParties(PATIENT_ID, CLINICIAN_ID, ROOM_ID, AppointmentSource.STAFF)
    assert authorize_booking(_admin(), named) == Success(expected)


def returns_default_room_when_free() -> None:
    chosen = choose_room(True, None, DEFAULT_ROOM_ID, [FIRST_ROOM_ID, DEFAULT_ROOM_ID], set())

    assert chosen == Success(DEFAULT_ROOM_ID)


def returns_first_free_active_room_in_code_order_when_default_is_busy() -> None:
    rooms = [FIRST_ROOM_ID, SECOND_ROOM_ID, DEFAULT_ROOM_ID]

    chosen = choose_room(True, None, DEFAULT_ROOM_ID, rooms, {DEFAULT_ROOM_ID, FIRST_ROOM_ID})

    assert chosen == Success(SECOND_ROOM_ID)


def returns_first_free_room_when_clinician_has_no_default() -> None:
    chosen = choose_room(True, None, None, [FIRST_ROOM_ID, SECOND_ROOM_ID], {FIRST_ROOM_ID})

    assert chosen == Success(SECOND_ROOM_ID)


def returns_no_room_available_when_all_busy() -> None:
    rooms = [FIRST_ROOM_ID, SECOND_ROOM_ID]

    chosen = choose_room(True, None, FIRST_ROOM_ID, rooms, {FIRST_ROOM_ID, SECOND_ROOM_ID})

    assert chosen == Failure.no_room_available()


def returns_no_room_available_when_department_has_no_room() -> None:
    assert choose_room(True, None, None, [], set()) == Failure.no_room_available()


def returns_no_room_when_type_needs_none() -> None:
    chosen = choose_room(False, None, DEFAULT_ROOM_ID, [DEFAULT_ROOM_ID], set())

    assert chosen == Success(None)


def returns_named_room_when_one_is_named_even_though_default_is_free() -> None:
    chosen = choose_room(True, ROOM_ID, DEFAULT_ROOM_ID, [DEFAULT_ROOM_ID], set())

    assert chosen == Success(ROOM_ID)


def returns_text_with_hospital_local_time_only_when_booked() -> None:
    starts_at = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)

    text = booked_notification_text(starts_at, ZoneInfo("Europe/Berlin"))

    assert text == "Your appointment is on 2030-01-07 at 11:00 (Europe/Berlin)."


def returns_own_calendar_when_clinician_names_themself() -> None:
    named = NamedParties(patient_id=PATIENT_ID, clinician_id=CLINICIAN_ID, room_id=None)

    expected = BookingParties(PATIENT_ID, CLINICIAN_ID, None, AppointmentSource.STAFF)
    assert authorize_booking(_clinician(), named) == Success(expected)


def returns_forbidden_when_clinician_has_no_profile() -> None:
    actor = BookingActor(Role.CLINICIAN, uuid4(), None)
    named = NamedParties(patient_id=PATIENT_ID, clinician_id=None, room_id=None)

    assert authorize_booking(actor, named) == Failure.forbidden()


def returns_first_of_several_free_rooms_when_clinician_has_no_default() -> None:
    rooms = [FIRST_ROOM_ID, SECOND_ROOM_ID, DEFAULT_ROOM_ID]

    chosen = choose_room(True, None, None, rooms, set())

    assert chosen == Success(FIRST_ROOM_ID)


def returns_named_room_when_clinician_names_one() -> None:
    named = NamedParties(patient_id=PATIENT_ID, clinician_id=None, room_id=ROOM_ID)

    expected = BookingParties(PATIENT_ID, CLINICIAN_ID, ROOM_ID, AppointmentSource.STAFF)
    assert authorize_booking(_clinician(), named) == Success(expected)


def returns_invalid_input_when_admin_names_no_patient() -> None:
    named = NamedParties(patient_id=None, clinician_id=CLINICIAN_ID, room_id=None)

    expected = Failure.invalid_input([FieldMessage("patient_id", "A patient is required.")])
    assert authorize_booking(_admin(), named) == expected


def returns_both_messages_in_order_when_admin_names_neither() -> None:
    named = NamedParties(patient_id=None, clinician_id=None, room_id=None)

    expected = Failure.invalid_input(
        [
            FieldMessage("patient_id", "A patient is required."),
            FieldMessage("clinician_id", "A clinician is required."),
        ]
    )
    assert authorize_booking(_admin(), named) == expected
