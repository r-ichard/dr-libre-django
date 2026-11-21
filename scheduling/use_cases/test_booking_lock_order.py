"""Section 5.2: one lock order, clinicians then patient then rooms. A verification of a patient
and a normal booking of the same patient must not wait for each other in a circle."""

from collections.abc import Callable
from datetime import timedelta
from threading import Barrier, Thread

import pytest
from django.db import connection, connections, transaction

from scheduling.domain.failure import Failure, Result, Success
from scheduling.models import BookingHold, User
from scheduling.models.access import VerificationCode
from scheduling.models.builders import STARTS_AT, Clinic, make, make_clinic
from scheduling.use_cases.booking_codes import hash_code
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.use_cases.test_booking_support import (
    NOW,
    THIRTY_MINUTES,
    VISITOR_EMAIL,
    _at,
    _verify,
)

pytestmark = pytest.mark.django_db(transaction=True)

CODE = "123456"
USER_LOCK_PROBE = "SELECT 1 FROM scheduling_user WHERE email = %s FOR UPDATE NOWAIT"


def _hold_of_patient(clinic: Clinic) -> BookingHold:
    hold = make(
        "BookingHold",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=STARTS_AT,
        ends_at=STARTS_AT + THIRTY_MINUTES,
        visitor_email=VISITOR_EMAIL,
        expires_at=NOW + timedelta(minutes=10),
    )
    assert isinstance(hold, BookingHold)
    make(
        "VerificationCode",
        hold=hold,
        code_hash=hash_code(hold.pk, CODE),
        email=VISITOR_EMAIL,
        expires_at=NOW + timedelta(minutes=10),
    )
    return hold


def _probe_user_lock_from_another_connection() -> list[str]:
    outcome: list[str] = []

    def probe() -> None:
        try:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(USER_LOCK_PROBE, [VISITOR_EMAIL])
            outcome.append("free")
        except Exception as error:  # noqa: BLE001 - the probe reports any refusal as its outcome
            outcome.append(type(error).__name__)
        finally:
            connections.close_all()

    thread = Thread(target=probe)
    thread.start()
    thread.join()
    return outcome


def returns_user_row_unlocked_when_verification_finds_existing_patient(
    committed_rows: None,
) -> None:
    from scheduling.use_cases.booking_verification import _patient_of

    make("User", email=VISITOR_EMAIL)

    with transaction.atomic(), _at(NOW):
        found = _patient_of(BookingHold(visitor_email=VISITOR_EMAIL))
        outcome = _probe_user_lock_from_another_connection()

    assert isinstance(found, Success)
    assert outcome == ["free"]


def _run_together(work: list[Callable[[], Result[object]]]) -> list[Result[object]]:
    barrier = Barrier(len(work))
    results: list[Result[object] | None] = [None] * len(work)

    def worker(index: int) -> None:
        try:
            barrier.wait()
            with _at(NOW):
                results[index] = work[index]()
        finally:
            connections.close_all()

    threads = [Thread(target=worker, args=(index,)) for index in range(len(work))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert None not in results
    return [result for result in results if result is not None]


@pytest.mark.parametrize("attempt", range(20))
def returns_no_error_when_verification_races_booking_of_same_patient(
    committed_rows: None, attempt: int
) -> None:
    clinic = make_clinic()
    patient = make("User", email=VISITOR_EMAIL)
    assert isinstance(patient, User)
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    hold = _hold_of_patient(clinic)
    command = PlacementCommand(
        clinic.appointment_type.pk,
        STARTS_AT + timedelta(hours=1),
        clinic.clinician.pk,
        patient.pk,
        None,
    )

    results = _run_together(
        [lambda: _verify(hold.pk, CODE), lambda: place_appointment(command, admin)]
    )

    assert all(isinstance(result, Success | Failure) for result in results)
    assert VerificationCode.objects.count() <= 1
