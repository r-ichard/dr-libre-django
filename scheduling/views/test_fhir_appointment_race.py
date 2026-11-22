"""Task 23a, point 9: two clients book the same slot over FHIR at once, each in its own
connection and transaction. One gets 201, the other 409, the database holds one appointment.
Rows are committed, so cleanup is the one of the placement races."""

import json
from threading import Barrier, Thread

import pytest
from django.db import connections

from scheduling.models import Appointment, User
from scheduling.models.builders import STARTS_AT, Clinic, make_clinic, make_user
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, send, token_of

pytestmark = pytest.mark.django_db(transaction=True)

ATTEMPTS = range(10)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _body(clinic: Clinic, patient: User) -> dict[str, object]:
    return {
        "resourceType": "Appointment",
        "status": "proposed",
        "start": STARTS_AT.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "serviceType": [{"coding": [{"code": str(clinic.appointment_type.pk)}]}],
        "participant": [
            {"actor": {"reference": f"Patient/{patient.pk}"}, "status": "accepted"},
            {
                "actor": {"reference": f"Practitioner/{clinic.clinician.user_id}"},
                "status": "accepted",
            },
        ],
    }


@pytest.mark.parametrize("attempt", ATTEMPTS)
def returns_201_for_one_and_409_for_the_other_when_two_clients_book_the_same_slot_together(
    committed_rows: None, attempt: int
) -> None:
    clinic = make_clinic()
    rivals = [clinic.patient, make_user(role="PATIENT")]
    requests = [(_body(clinic, rival), token_of(rival)) for rival in rivals]
    barrier = Barrier(len(requests))
    statuses: list[int] = []

    def worker(body: dict[str, object], token: str) -> None:
        try:
            barrier.wait()
            statuses.append(send("post", "/fhir/Appointment", body, token).status_code)
        finally:
            connections.close_all()

    threads = [Thread(target=worker, args=request) for request in requests]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(statuses) == [201, 409], json.dumps(statuses)
    assert Appointment.objects.count() == 1
