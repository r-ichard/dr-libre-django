"""Task 23a, spec 15.2 to 15.6: Appointment over FHIR. Reads follow the caller's role, a clinical
note reaches its own clinician only, the three origins are one resource type, and a booking runs
the same use cases as the screens."""

from datetime import UTC, datetime, timedelta

import pytest

from scheduling.models import Appointment, WaitlistEntry
from scheduling.models.builders import STARTS_AT, make, make_clinic, make_user
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, get, send, token_of

pytestmark = pytest.mark.django_db

PLANTED_NOTE = "planted clinical note: zebra-17"
MONDAY_TEN = "2030-01-07T10:00:00Z"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _booked(clinic: object, **fields: object) -> Appointment:
    row = make(
        "Appointment",
        clinician=clinic.clinician,  # type: ignore[attr-defined]
        appointment_type=clinic.appointment_type,  # type: ignore[attr-defined]
        **fields,
    )
    assert isinstance(row, Appointment)
    return row


def _ids(response: object) -> list[str]:
    return [item["resource"]["id"] for item in response.json().get("entry", [])]  # type: ignore[attr-defined]


def returns_401_when_appointment_is_read_or_searched_without_token() -> None:
    row = _booked(make_clinic())

    assert get(f"/fhir/Appointment/{row.pk}").status_code == 401
    assert get("/fhir/Appointment").status_code == 401


def returns_booked_appointment_with_participants_and_no_store_when_patient_reads_own() -> None:
    clinic = make_clinic()
    row = _booked(clinic, patient=clinic.patient, patient_reason="Cough")

    response = get(f"/fhir/Appointment/{row.pk}", token_of(clinic.patient))

    body = response.json()
    assert response.status_code == 200
    assert body["resourceType"] == "Appointment"
    assert body["status"] == "booked"
    assert body["start"] == MONDAY_TEN
    assert body["end"] == "2030-01-07T10:30:00Z"
    assert body["serviceType"][0]["coding"][0]["code"] == str(clinic.appointment_type.pk)
    assert body["reasonCode"][0]["text"] == "Cough"
    references = {item["actor"]["reference"] for item in body["participant"]}
    assert {
        f"Patient/{clinic.patient.pk}",
        f"Practitioner/{clinic.clinician.user_id}",
    } <= references
    assert response["Cache-Control"] == "no-store"
    assert response["ETag"] == f'W/"{row.version}"'


def returns_only_own_appointments_and_own_total_when_patient_searches() -> None:
    clinic = make_clinic()
    mine = _booked(clinic, patient=clinic.patient)
    _booked(
        clinic,
        patient=make_user(role="PATIENT"),
        starts_at=STARTS_AT + timedelta(hours=1),
        ends_at=STARTS_AT + timedelta(hours=2),
    )

    response = get("/fhir/Appointment", token_of(clinic.patient))

    assert response.json()["total"] == 1
    assert _ids(response) == [str(mine.pk)]


def returns_every_appointment_when_admin_searches() -> None:
    clinic = make_clinic()
    _booked(clinic)

    assert get("/fhir/Appointment", token_of(role="ADMIN")).json()["total"] == 1


def returns_only_own_calendar_when_clinician_searches() -> None:
    clinic = make_clinic()
    mine = _booked(clinic, patient=clinic.patient)
    _booked(make_clinic(), patient=make_user(role="PATIENT"))

    response = get("/fhir/Appointment", token_of(clinic.clinician.user))

    assert response.json()["total"] == 1
    assert _ids(response) == [str(mine.pk)]


def returns_no_other_patients_waitlist_entry_when_patient_searches_waitlist() -> None:
    clinic = make_clinic()
    mine = make("WaitlistEntry", patient=clinic.patient, appointment_type=clinic.appointment_type)
    make(
        "WaitlistEntry",
        patient=make_user(role="PATIENT"),
        appointment_type=clinic.appointment_type,
    )

    response = get("/fhir/Appointment?status=waitlist", token_of(clinic.patient))

    assert response.json()["total"] == 1
    assert _ids(response) == [str(mine.pk)]


def returns_412_when_unchanged_body_carries_a_stale_version() -> None:
    clinic = make_clinic()
    row = _booked(
        clinic,
        patient=clinic.patient,
        starts_at=STARTS_AT + timedelta(days=30),
        ends_at=STARTS_AT + timedelta(days=30, minutes=30),
    )
    token = token_of(clinic.patient)
    body = get(f"/fhir/Appointment/{row.pk}", token).json()

    stale = send(
        "put", f"/fhir/Appointment/{row.pk}", body, token, **{"If-Match": f'W/"{row.version + 5}"'}
    )
    current = send(
        "put", f"/fhir/Appointment/{row.pk}", body, token, **{"If-Match": f'W/"{row.version}"'}
    )

    assert (stale.status_code, current.status_code) == (412, 200)


def returns_403_when_patient_reads_another_patients_appointment() -> None:
    clinic = make_clinic()
    row = _booked(clinic, patient=make_user(role="PATIENT"))

    assert get(f"/fhir/Appointment/{row.pk}", token_of(clinic.patient)).status_code == 403


def returns_never_another_patient_when_patient_includes_participants() -> None:
    clinic = make_clinic()
    mine = _booked(clinic, patient=clinic.patient)

    response = get("/fhir/Appointment?_include=Appointment:patient", token_of(clinic.patient))

    included = [
        e["resource"] for e in response.json()["entry"] if e["resource"]["id"] != str(mine.pk)
    ]
    assert [item["resourceType"] for item in included] == ["Patient"]
    assert included[0]["id"] == str(clinic.patient.pk)


@pytest.mark.parametrize("role", ["PATIENT", "ADMIN", "OTHER_CLINICIAN"])
def returns_no_clinical_note_to_anyone_but_the_appointments_clinician(role: str) -> None:
    clinic = make_clinic()
    row = _booked(clinic, patient=clinic.patient)
    make("ClinicalNote", appointment=row, clinical_notes=PLANTED_NOTE)
    other = make_clinic().clinician.user
    caller = {
        "PATIENT": clinic.patient,
        "ADMIN": make_user(role="ADMIN"),
        "OTHER_CLINICIAN": other,
    }[role]
    token = token_of(caller)

    read = get(f"/fhir/Appointment/{row.pk}", token)
    search = get("/fhir/Appointment?_include=Appointment:patient", token)

    assert PLANTED_NOTE not in read.content.decode()
    assert PLANTED_NOTE not in search.content.decode()


def returns_clinical_note_as_comment_when_the_appointments_clinician_reads_it() -> None:
    clinic = make_clinic()
    row = _booked(clinic, patient=clinic.patient)
    make("ClinicalNote", appointment=row, clinical_notes=PLANTED_NOTE)

    response = get(f"/fhir/Appointment/{row.pk}", token_of(clinic.clinician.user))

    assert response.json()["comment"] == PLANTED_NOTE


def returns_hold_as_pending_for_staff_and_never_for_a_patient() -> None:
    clinic = make_clinic()
    hold = make("BookingHold", clinician=clinic.clinician, appointment_type=clinic.appointment_type)

    staff = get("/fhir/Appointment?status=pending", token_of(role="ADMIN"))
    patient = get("/fhir/Appointment?status=pending", token_of(clinic.patient))

    assert _ids(staff) == [str(hold.pk)]
    assert _ids(patient) == []


def returns_accepted_entry_once_under_booked_with_the_entrys_id() -> None:
    clinic = make_clinic()
    entry = make(
        "WaitlistEntry",
        patient=clinic.patient,
        appointment_type=clinic.appointment_type,
        status="BOOKED",
    )
    row = _booked(clinic, patient=clinic.patient, waitlist_entry=entry)

    response = get("/fhir/Appointment?status=booked", token_of(clinic.patient))

    assert _ids(response) == [str(entry.pk)]
    assert response.json()["total"] == 1
    assert row.pk != entry.pk


def returns_waitlist_status_and_requested_period_when_patient_waits() -> None:
    clinic = make_clinic()
    entry = make("WaitlistEntry", patient=clinic.patient, appointment_type=clinic.appointment_type)

    response = get("/fhir/Appointment?status=waitlist", token_of(clinic.patient))

    assert _ids(response) == [str(entry.pk)]
    period = response.json()["entry"][0]["resource"]["requestedPeriod"][0]
    assert period["start"] == MONDAY_TEN


def returns_201_booked_with_location_and_etag_when_patient_books_a_start_with_practitioner() -> (
    None
):
    clinic = make_clinic()
    body = _booking_body(clinic)

    response = send("post", "/fhir/Appointment", body, token_of(clinic.patient))

    created = Appointment.objects.get()
    assert response.status_code == 201
    assert response.json()["status"] == "booked"
    assert response["Location"].endswith(f"/fhir/Appointment/{created.pk}")
    assert response["ETag"] == f'W/"{created.version}"'
    assert created.patient_id == clinic.patient.pk
    assert created.ends_at == datetime(2030, 1, 7, 10, 30, tzinfo=UTC)


def returns_403_and_no_appointment_when_patient_books_for_another_patient() -> None:
    clinic = make_clinic()
    stranger = make_user(role="PATIENT")
    body = _booking_body(clinic, patient=stranger)

    response = send("post", "/fhir/Appointment", body, token_of(clinic.patient))

    assert response.status_code == 403
    assert not Appointment.objects.exists()


def returns_201_for_the_first_and_409_for_the_second_when_the_same_slot_is_booked_twice() -> None:
    clinic = make_clinic()
    second = make_user(role="PATIENT")

    first_answer = send(
        "post", "/fhir/Appointment", _booking_body(clinic), token_of(clinic.patient)
    )
    second_answer = send(
        "post", "/fhir/Appointment", _booking_body(clinic, patient=second), token_of(second)
    )

    assert (first_answer.status_code, second_answer.status_code) == (201, 409)
    assert Appointment.objects.count() == 1


def returns_400_naming_end_when_client_sends_an_end_that_is_not_start_plus_duration() -> None:
    clinic = make_clinic()
    row = _booked(
        clinic,
        patient=clinic.patient,
        starts_at=STARTS_AT + timedelta(days=7),
        ends_at=STARTS_AT + timedelta(days=7, minutes=30),
    )
    token = token_of(clinic.patient)
    body = get(f"/fhir/Appointment/{row.pk}", token).json()
    body["end"] = "2030-01-14T12:00:00Z"

    response = send(
        "put", f"/fhir/Appointment/{row.pk}", body, token, **{"If-Match": f'W/"{row.version}"'}
    )

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Appointment.end"]


def returns_412_when_cancel_carries_a_stale_version() -> None:
    clinic = make_clinic()
    row = _booked(
        clinic,
        patient=clinic.patient,
        starts_at=STARTS_AT + timedelta(days=30),
        ends_at=STARTS_AT + timedelta(days=30, minutes=30),
    )
    token = token_of(clinic.patient)
    body = get(f"/fhir/Appointment/{row.pk}", token).json()
    body.update(status="cancelled", cancelationReason={"text": "Travel"})

    response = send(
        "put", f"/fhir/Appointment/{row.pk}", body, token, **{"If-Match": f'W/"{row.version + 5}"'}
    )

    assert response.status_code == 412


def returns_reason_on_the_row_when_patient_books_with_reason_code() -> None:
    clinic = make_clinic()
    body = _booking_body(clinic)
    body["reasonCode"] = [{"text": "Cough"}]

    send("post", "/fhir/Appointment", body, token_of(clinic.patient))

    assert Appointment.objects.get().patient_reason == "Cough"


def returns_201_and_entry_with_window_and_preferred_clinician_when_patient_joins_waitlist() -> None:
    clinic = make_clinic()
    body = _booking_body(clinic)
    del body["start"]
    body.update(
        status="waitlist",
        requestedPeriod=[{"start": MONDAY_TEN, "end": "2030-01-09T10:00:00Z"}],
    )

    response = send("post", "/fhir/Appointment", body, token_of(clinic.patient))

    entry = WaitlistEntry.objects.get()
    assert response.status_code == 201
    assert response.json()["status"] == "waitlist"
    assert entry.patient_id == clinic.patient.pk
    assert entry.earliest_at == datetime(2030, 1, 7, 10, tzinfo=UTC)
    assert entry.latest_at == datetime(2030, 1, 9, 10, tzinfo=UTC)
    assert entry.preferred_clinician_id == clinic.clinician.pk


def _later(clinic: object, **fields: object) -> Appointment:
    return _booked(
        clinic,
        patient=clinic.patient,  # type: ignore[attr-defined]
        starts_at=STARTS_AT + timedelta(days=30),
        ends_at=STARTS_AT + timedelta(days=30, minutes=30),
        **fields,
    )


def _put(row: Appointment, token: str, **changes: object) -> object:
    body = get(f"/fhir/Appointment/{row.pk}", token).json()
    body.update(changes)
    return send(
        "put", f"/fhir/Appointment/{row.pk}", body, token, **{"If-Match": f'W/"{row.version}"'}
    )


def returns_200_and_moved_row_when_patient_reschedules_a_week_later() -> None:
    clinic = make_clinic()
    row = _later(clinic)

    response = _put(
        row,
        token_of(clinic.patient),
        start="2030-02-11T10:00:00Z",
        end="2030-02-11T10:30:00Z",
    )

    row.refresh_from_db()
    assert response.status_code == 200  # type: ignore[attr-defined]
    assert row.starts_at == datetime(2030, 2, 11, 10, tzinfo=UTC)
    assert row.ends_at == datetime(2030, 2, 11, 10, 30, tzinfo=UTC)


def returns_200_and_cancellation_reason_when_patient_cancels() -> None:
    clinic = make_clinic()
    row = _later(clinic)

    response = _put(
        row, token_of(clinic.patient), status="cancelled", cancelationReason={"text": "Travel"}
    )

    row.refresh_from_db()
    assert response.status_code == 200  # type: ignore[attr-defined]
    assert (row.status, row.cancellation_reason) == ("CANCELLED", "Travel")
    assert response.json()["cancelationReason"] == {"text": "Travel"}  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("fhir", "before", "after"),
    [
        ("checked-in", "BOOKED", "CHECKED_IN"),
        ("fulfilled", "CHECKED_IN", "COMPLETED"),
        ("noshow", "BOOKED", "NO_SHOW"),
    ],
)
def returns_200_and_new_status_when_clinician_moves_the_visit_along(
    fhir: str, before: str, after: str
) -> None:
    clinic = make_clinic()
    row = _later(clinic, status=before)

    response = _put(row, token_of(clinic.clinician.user), status=fhir)

    row.refresh_from_db()
    assert response.status_code == 200  # type: ignore[attr-defined]
    assert row.status == after


def returns_409_and_unchanged_row_when_status_is_not_allowed_from_the_current_one() -> None:
    clinic = make_clinic()
    row = _later(clinic, status="CANCELLED", cancelled_at=NOW, cancellation_reason="Gone")

    response = _put(row, token_of(clinic.clinician.user), status="fulfilled")

    row.refresh_from_db()
    assert response.status_code == 409  # type: ignore[attr-defined]
    assert row.status == "CANCELLED"


def _booking_body(clinic: object, patient: object = None) -> dict[str, object]:
    person = patient or clinic.patient  # type: ignore[attr-defined]
    return {
        "resourceType": "Appointment",
        "status": "proposed",
        "start": MONDAY_TEN,
        "serviceType": [{"coding": [{"code": str(clinic.appointment_type.pk)}]}],  # type: ignore[attr-defined]
        "participant": [
            {"actor": {"reference": f"Patient/{person.pk}"}, "status": "accepted"},  # type: ignore[union-attr]
            {
                "actor": {"reference": f"Practitioner/{clinic.clinician.user_id}"},  # type: ignore[attr-defined]
                "status": "accepted",
            },
        ],
    }
