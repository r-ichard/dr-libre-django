"""Section 5.2 to 5.5: placing an appointment, step by step, stopping at the first failure."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from django.db.models import F

from scheduling.domain.failure import Failure, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import (
    Appointment,
    AuditLogEntry,
    ClinicianProfile,
    Notification,
    User,
)
from scheduling.models.builders import STARTS_AT, Clinic, add_clinician, make, make_clinic
from scheduling.use_cases import placement, placement_checks
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
SLOT = STARTS_AT
THIRTY_MINUTES = timedelta(minutes=30)


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-place", NOW)):
        yield


def _command(clinic: Clinic, **overrides: object) -> PlacementCommand:
    fields: dict[str, object] = {
        "appointment_type_id": clinic.appointment_type.pk,
        "starts_at": SLOT,
        "clinician_id": clinic.clinician.pk,
        "patient_id": None,
        "room_id": None,
    }
    return PlacementCommand(**{**fields, **overrides})  # type: ignore[arg-type]


def _admin() -> User:
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    return admin


def _book_for(clinic: Clinic, **overrides: object) -> Success[Appointment] | Failure:
    """An admin books the clinic's patient, so patient rules do not apply."""
    command = _command(clinic, patient_id=clinic.patient.pk, **overrides)
    return place_appointment(command, _admin())


def _busy(clinic: Clinic, **overrides: object) -> Appointment:
    fields = {
        "appointment_type": clinic.appointment_type,
        "starts_at": SLOT,
        "ends_at": SLOT + THIRTY_MINUTES,
    }
    row = make("Appointment", **{**fields, **overrides})
    assert isinstance(row, Appointment)
    return row


def _booked(result: Success[Appointment] | Failure) -> Appointment:
    assert isinstance(result, Success), result
    return result.value


def returns_booked_appointment_with_end_start_plus_duration_when_patient_books() -> None:
    clinic = make_clinic(type_fields={"duration_minutes": 45})

    result = place_appointment(_command(clinic), clinic.patient)

    appointment = _booked(result)
    assert appointment.status == "BOOKED"
    assert appointment.source == "ONLINE"
    assert appointment.patient_id == clinic.patient.pk
    assert appointment.starts_at == SLOT
    assert appointment.ends_at == SLOT + timedelta(minutes=45)


def returns_forbidden_when_patient_names_another_patient() -> None:
    clinic = make_clinic()
    other = make("User")

    result = place_appointment(_command(clinic, patient_id=other.pk), clinic.patient)

    assert result == Failure.forbidden()
    assert Appointment.objects.count() == 0


def returns_staff_booking_for_named_patient_when_admin_books() -> None:
    clinic = make_clinic()

    appointment = _booked(_book_for(clinic))

    assert (appointment.patient_id, appointment.source) == (clinic.patient.pk, "STAFF")


def returns_not_found_when_type_inactive() -> None:
    clinic = make_clinic(type_fields={"is_active": False})

    assert _book_for(clinic) == Failure.not_found()


def returns_not_found_when_clinician_in_other_department() -> None:
    clinic = make_clinic()
    stranger = add_clinician(make("Department"))

    assert _book_for(clinic, clinician_id=stranger.pk) == Failure.not_found()


def returns_not_found_when_clinician_user_inactive() -> None:
    clinic = make_clinic()
    gone = add_clinician(clinic.department, user=make("User", role="CLINICIAN", is_active=False))

    assert _book_for(clinic, clinician_id=gone.pk) == Failure.not_found()


def returns_not_found_when_patient_inactive() -> None:
    clinic = make_clinic()
    inactive = make("User", is_active=False)

    result = place_appointment(_command(clinic, patient_id=inactive.pk), _admin())

    assert result == Failure.not_found()


def returns_not_found_when_patient_is_not_role_patient() -> None:
    clinic = make_clinic()
    colleague = make("User", role="CLINICIAN")

    result = place_appointment(_command(clinic, patient_id=colleague.pk), _admin())

    assert result == Failure.not_found()


def returns_not_found_when_named_room_inactive() -> None:
    clinic = make_clinic()
    room = make("Room", department=clinic.department, is_active=False)

    assert _book_for(clinic, room_id=room.pk) == Failure.not_found()


def returns_not_found_when_named_room_in_other_department() -> None:
    clinic = make_clinic()
    room = make("Room", department=make("Department"))

    assert _book_for(clinic, room_id=room.pk) == Failure.not_found()


def returns_not_found_not_conflict_when_type_inactive_and_slot_taken() -> None:
    clinic = make_clinic(type_fields={"is_active": False})
    _busy(clinic, clinician=clinic.clinician)

    assert _book_for(clinic) == Failure.not_found()


def returns_conflict_naming_clinician_when_clinician_busy() -> None:
    clinic = make_clinic()
    _busy(clinic, clinician=clinic.clinician)

    assert _book_for(clinic) == Failure.conflict(["clinician"])


def returns_conflict_naming_patient_when_patient_busy() -> None:
    clinic = make_clinic()
    _busy(clinic, patient=clinic.patient, clinician=add_clinician(clinic.department))

    assert _book_for(clinic) == Failure.conflict(["patient"])


def returns_conflict_naming_room_when_named_room_busy() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    room = make("Room", department=clinic.department)
    _busy(clinic, room=room, clinician=add_clinician(clinic.department))

    assert _book_for(clinic, room_id=room.pk) == Failure.conflict(["room"])


def returns_conflict_naming_all_three_when_all_three_overlap() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    room = make("Room", department=clinic.department)
    _busy(clinic, clinician=clinic.clinician)
    _busy(clinic, patient=clinic.patient, clinician=add_clinician(clinic.department))
    _busy(clinic, room=room, clinician=add_clinician(clinic.department))

    result = _book_for(clinic, room_id=room.pk)

    assert result == Failure.conflict(["clinician", "patient", "room"])


def returns_conflict_not_error_when_constraint_catches_what_the_check_missed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = make_clinic()
    _busy(clinic, clinician=clinic.clinician)
    monkeypatch.setattr(placement_checks, "find_conflicts", lambda *_arguments: [])
    # A real race is stale for the availability check too, so it must miss the busy slot as well.
    monkeypatch.setattr(placement_checks, "violated_booking_rules", lambda *_arguments: [])

    result = _book_for(clinic)

    assert result == Failure.conflict(["clinician"])
    assert Appointment.objects.count() == 1


def returns_rule_violation_lead_time_too_short_when_patient_books_in_119_minutes() -> None:
    clinic = make_clinic()
    almost = RequestContext("corr-late", SLOT - timedelta(minutes=119))

    with bind_request_context(almost):
        result = place_appointment(_command(clinic), clinic.patient)

    assert result == Failure.rule_violation(["lead_time_too_short"])


def returns_booking_when_patient_books_in_exactly_120_minutes() -> None:
    clinic = make_clinic()
    exactly = RequestContext("corr-limit", SLOT - timedelta(minutes=120))

    with bind_request_context(exactly):
        result = place_appointment(_command(clinic), clinic.patient)

    assert isinstance(result, Success)


def returns_rule_violation_when_patient_has_three_open_online_bookings() -> None:
    clinic = make_clinic()
    for days in (1, 2, 3):
        later = SLOT + timedelta(days=days)
        _busy(
            clinic,
            patient=clinic.patient,
            clinician=add_clinician(clinic.department),
            starts_at=later,
            ends_at=later + THIRTY_MINUTES,
        )

    result = place_appointment(_command(clinic), clinic.patient)

    assert result == Failure.rule_violation(["too_many_open_bookings"])


def returns_rule_violation_when_type_not_bookable_online_and_patient_books() -> None:
    clinic = make_clinic(type_fields={"is_bookable_online": False})

    result = place_appointment(_command(clinic), clinic.patient)

    assert result == Failure.rule_violation(["type_not_bookable_online"])


def returns_every_violated_rule_when_several_fail() -> None:
    clinic = make_clinic(type_fields={"is_bookable_online": False})
    off_the_grid = SLOT + timedelta(minutes=5)

    result = place_appointment(_command(clinic, starts_at=off_the_grid), clinic.patient)

    assert result == Failure.rule_violation(["type_not_bookable_online", "outside_availability"])


def returns_rule_violation_outside_availability_when_staff_books_off_the_grid() -> None:
    clinic = make_clinic()
    off_the_grid = SLOT + timedelta(minutes=5)

    assert _book_for(clinic, starts_at=off_the_grid) == Failure.rule_violation(
        ["outside_availability"]
    )


def returns_booking_when_staff_books_inside_lead_time() -> None:
    clinic = make_clinic()
    soon = RequestContext("corr-soon", SLOT - timedelta(minutes=10))

    with bind_request_context(soon):
        result = _book_for(clinic)

    assert isinstance(result, Success)


def returns_default_room_when_type_needs_room_and_default_is_free() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    make("Room", department=clinic.department, code="a-first")
    default = make("Room", department=clinic.department, code="b-default")
    ClinicianProfile.objects.filter(pk=clinic.clinician.pk).update(
        version=F("version") + 1, default_room=default
    )

    assert _booked(_book_for(clinic)).room_id == default.pk


def returns_first_free_room_in_code_order_when_default_is_busy() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    default = make("Room", department=clinic.department, code="c-default")
    make("Room", department=clinic.department, code="b-second")
    first = make("Room", department=clinic.department, code="a-first")
    ClinicianProfile.objects.filter(pk=clinic.clinician.pk).update(
        version=F("version") + 1, default_room=default
    )
    _busy(clinic, room=default, clinician=add_clinician(clinic.department))

    assert _booked(_book_for(clinic)).room_id == first.pk


def returns_no_room_available_when_type_needs_room_and_none_free() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})

    assert _book_for(clinic) == Failure.no_room_available()
    assert Appointment.objects.count() == 0


def returns_no_room_when_type_needs_none() -> None:
    clinic = make_clinic()
    make("Room", department=clinic.department)

    assert _booked(_book_for(clinic)).room_id is None


def returns_audit_entry_without_free_text_when_booked() -> None:
    clinic = make_clinic()

    appointment = _booked(place_appointment(_command(clinic), clinic.patient))

    entry = AuditLogEntry.objects.get(action="appointment.book")
    assert entry.entity_type == "Appointment"
    assert entry.entity_id == str(appointment.pk)
    assert entry.actor_id == clinic.patient.pk
    assert entry.metadata["ids"]["patient_id"] == str(clinic.patient.pk)
    assert entry.metadata["statuses"] == {"appointment_status": "BOOKED", "source_status": "ONLINE"}


def returns_notification_with_title_and_time_only_when_booked() -> None:
    clinic = make_clinic()

    appointment = _booked(place_appointment(_command(clinic), clinic.patient))

    notification = Notification.objects.get()
    assert notification.recipient_id == clinic.patient.pk
    assert notification.kind == "SCHEDULE_CHANGED"
    assert notification.title == "Appointment booked"
    assert notification.body == "Your appointment is on 2030-01-07 at 11:00 (Europe/Berlin)."
    assert notification.appointment_id == appointment.pk


def returns_no_appointment_when_audit_write_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    clinic = make_clinic()

    def failing_audit(*_arguments: object) -> None:
        raise RuntimeError("audit down")

    monkeypatch.setattr(placement, "record_audit", failing_audit)

    with pytest.raises(RuntimeError):
        place_appointment(_command(clinic), clinic.patient)

    assert Appointment.objects.count() == 0
    assert Notification.objects.count() == 0


def _first_available(clinic: Clinic) -> Success[Appointment] | Failure:
    return place_appointment(_command(clinic, clinician_id=None), clinic.patient)


def returns_never_assigned_clinician_first_when_no_clinician_named() -> None:
    clinic = make_clinic()
    ClinicianProfile.objects.filter(pk=clinic.clinician.pk).update(
        version=F("version") + 1, last_assigned_at=NOW - timedelta(days=30)
    )
    fresh = add_clinician(clinic.department)

    assert _booked(_first_available(clinic)).clinician_id == fresh.pk


def returns_largest_idle_time_times_weight_next_when_all_assigned_before() -> None:
    clinic = make_clinic()
    ClinicianProfile.objects.filter(pk=clinic.clinician.pk).update(
        version=F("version") + 1, last_assigned_at=NOW - timedelta(hours=10)
    )
    heavy = add_clinician(
        clinic.department, round_robin_weight=5, last_assigned_at=NOW - timedelta(hours=3)
    )

    assert _booked(_first_available(clinic)).clinician_id == heavy.pk


def returns_source_round_robin_and_sets_last_assigned_at_to_now() -> None:
    clinic = make_clinic()

    appointment = _booked(_first_available(clinic))

    assert appointment.source == "ROUND_ROBIN"
    assert ClinicianProfile.objects.get(pk=appointment.clinician_id).last_assigned_at == NOW


def returns_free_clinician_when_the_never_assigned_one_is_busy() -> None:
    clinic = make_clinic()
    busy = add_clinician(clinic.department)
    _busy(clinic, clinician=busy)
    ClinicianProfile.objects.filter(pk=clinic.clinician.pk).update(
        version=F("version") + 1, last_assigned_at=NOW - timedelta(days=30)
    )

    assert _booked(_first_available(clinic)).clinician_id == clinic.clinician.pk


def returns_no_clinician_available_when_none_free() -> None:
    clinic = make_clinic()
    _busy(clinic, clinician=clinic.clinician)

    assert _first_available(clinic) == Failure.no_clinician_available()


def returns_audit_entry_for_assignment_time_when_first_available_books() -> None:
    clinic = make_clinic()

    appointment = _booked(_first_available(clinic))

    entry = AuditLogEntry.objects.get(action="clinician.round_robin_assigned")
    assert entry.entity_id == str(appointment.clinician_id)
    assert entry.metadata["changed_fields"] == ["last_assigned_at"]
