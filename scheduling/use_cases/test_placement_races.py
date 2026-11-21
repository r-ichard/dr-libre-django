"""Section 5.2: two real transactions race, exactly one wins each time.

Rows are committed from two threads, so the test transaction cannot hold them. The flush of
transaction=True would TRUNCATE the append-only audit table, so the fixture cleans by hand.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from threading import Barrier, Thread

import pytest
from django.db import connection, connections
from django.db.models import F

from scheduling.domain.failure import Failure, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, ClinicianProfile, User
from scheduling.models.builders import STARTS_AT, Clinic, add_clinician, make, make_clinic
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db(transaction=True)

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
ATTEMPTS = range(20)
AUDIT_TABLE = "scheduling_auditlogentry"
THIRTY_MINUTES = timedelta(minutes=30)

type Placement = Callable[[], Success[Appointment] | Failure]


@pytest.fixture(scope="module")
def committed_rows(django_db_setup: None, django_db_blocker: object) -> Iterator[None]:
    """Module scope, so the trigger is off before the first flush of transaction=True and back
    on after the last one; a function-scoped fixture would be torn down before the flush."""
    with django_db_blocker.unblock():  # type: ignore[attr-defined]
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {AUDIT_TABLE} DISABLE TRIGGER USER")
        try:
            yield
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"ALTER TABLE {AUDIT_TABLE} ENABLE TRIGGER USER")


def _run_together(placements: list[Placement]) -> list[Success[Appointment] | Failure]:
    barrier = Barrier(len(placements))
    results: list[Success[Appointment] | Failure | None] = [None] * len(placements)

    def worker(index: int) -> None:
        try:
            barrier.wait()
            with bind_request_context(RequestContext(f"corr-race-{index}", NOW)):
                results[index] = placements[index]()
        finally:
            connections.close_all()

    threads = [Thread(target=worker, args=(index,)) for index in range(len(placements))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert None not in results
    return [result for result in results if result is not None]


def _book(clinic: Clinic, actor: User, **overrides: object) -> Placement:
    fields: dict[str, object] = {
        "appointment_type_id": clinic.appointment_type.pk,
        "starts_at": STARTS_AT,
        "clinician_id": clinic.clinician.pk,
        "patient_id": None,
        "room_id": None,
    }
    command = PlacementCommand(**{**fields, **overrides})  # type: ignore[arg-type]
    return lambda: place_appointment(command, actor)


def _admin() -> User:
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    return admin


def _patient() -> User:
    patient = make("User")
    assert isinstance(patient, User)
    return patient


def _conflicts(results: list[Success[Appointment] | Failure]) -> list[Failure]:
    return [result for result in results if isinstance(result, Failure)]


@pytest.mark.parametrize("attempt", ATTEMPTS)
def returns_exactly_one_booking_when_two_race_for_same_clinician(
    committed_rows: None, attempt: int
) -> None:
    clinic = make_clinic()
    other_patient = _patient()

    results = _run_together([_book(clinic, clinic.patient), _book(clinic, other_patient)])

    assert Appointment.objects.count() == 1
    assert _conflicts(results) == [Failure.conflict(["clinician"])]


@pytest.mark.parametrize("attempt", ATTEMPTS)
def returns_exactly_one_booking_when_two_race_for_same_patient(
    committed_rows: None, attempt: int
) -> None:
    clinic = make_clinic()
    second = add_clinician(clinic.department)
    admin = _admin()
    first_try = _book(clinic, admin, patient_id=clinic.patient.pk)
    second_try = _book(clinic, admin, patient_id=clinic.patient.pk, clinician_id=second.pk)

    results = _run_together([first_try, second_try])

    assert Appointment.objects.count() == 1
    assert _conflicts(results) == [Failure.conflict(["patient"])]


@pytest.mark.parametrize("attempt", ATTEMPTS)
def returns_exactly_one_booking_when_two_race_for_same_named_room(
    committed_rows: None, attempt: int
) -> None:
    clinic = make_clinic()
    second = add_clinician(clinic.department)
    room = make("Room", department=clinic.department)
    admin = _admin()
    first_try = _book(clinic, admin, patient_id=_patient().pk, room_id=room.pk)
    second_try = _book(
        clinic, admin, patient_id=_patient().pk, room_id=room.pk, clinician_id=second.pk
    )

    results = _run_together([first_try, second_try])

    assert Appointment.objects.count() == 1
    assert _conflicts(results) == [Failure.conflict(["room"])]


@pytest.mark.parametrize("attempt", ATTEMPTS)
def returns_both_booked_with_different_rooms_when_two_clinicians_share_a_default_room(
    committed_rows: None, attempt: int
) -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    second = add_clinician(clinic.department)
    shared = make("Room", department=clinic.department, code="a-shared")
    make("Room", department=clinic.department, code="b-spare")
    ClinicianProfile.objects.filter(pk__in=[clinic.clinician.pk, second.pk]).update(
        version=F("version") + 1, default_room=shared
    )
    first_try = _book(clinic, clinic.patient)
    second_try = _book(clinic, _patient(), clinician_id=second.pk)

    results = _run_together([first_try, second_try])

    assert all(isinstance(result, Success) for result in results)
    assert Appointment.objects.values("room_id").distinct().count() == 2


@pytest.mark.parametrize("attempt", ATTEMPTS)
def returns_one_booking_when_patient_with_two_open_races_two_more(
    committed_rows: None, attempt: int
) -> None:
    clinic = make_clinic()
    second = add_clinician(clinic.department)
    for days in (1, 2):
        later = STARTS_AT + timedelta(days=days)
        make(
            "Appointment",
            patient=clinic.patient,
            clinician=add_clinician(clinic.department),
            appointment_type=clinic.appointment_type,
            starts_at=later,
            ends_at=later + THIRTY_MINUTES,
        )
    hour_later = STARTS_AT + timedelta(hours=1)
    first_try = _book(clinic, clinic.patient)
    second_try = _book(clinic, clinic.patient, clinician_id=second.pk, starts_at=hour_later)

    results = _run_together([first_try, second_try])

    assert Appointment.objects.count() == 3
    assert _conflicts(results) == [Failure.rule_violation(["too_many_open_bookings"])]


@pytest.mark.parametrize("attempt", ATTEMPTS)
def returns_both_booked_with_different_clinicians_when_two_patients_race_first_available(
    committed_rows: None, attempt: int
) -> None:
    clinic = make_clinic()
    add_clinician(clinic.department)
    first_try = _book(clinic, clinic.patient, clinician_id=None)
    second_try = _book(clinic, _patient(), clinician_id=None)

    results = _run_together([first_try, second_try])

    assert all(isinstance(result, Success) for result in results)
    assert Appointment.objects.values("clinician_id").distinct().count() == 2
