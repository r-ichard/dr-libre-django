"""Task 24, spec 15.2, 15.4, 15.5: `Communication` is a notification, read by its recipient only,
and its `received` time is set once through the `mark_read` use case."""

from datetime import datetime

import pytest

from scheduling.models import Appointment, Notification, User, WaitlistEntry
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases.test_waitlist_support import (
    _booked_slot,
    _cancelled_slot,
    _offered_entry,
)
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, get, send, token_of

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _notification(recipient: User, **fields: object) -> Notification:
    fields = {
        "kind": "WAITLIST_OFFERED",
        "title": "A slot is free",
        "body": "Tuesday 9:00",
        **fields,
    }
    row = make("Notification", recipient=recipient, **fields)
    assert isinstance(row, Notification)
    return row


def _accept(entry: WaitlistEntry) -> dict[str, object]:
    return {
        "resourceType": "AppointmentResponse",
        "appointment": {"reference": f"Appointment/{entry.pk}"},
        "actor": {"reference": f"Patient/{entry.patient_id}"},
        "participantStatus": "accepted",
    }


def _patient() -> User:
    user = make("User", role="PATIENT")
    assert isinstance(user, User)
    return user


def returns_payload_category_and_sent_when_recipient_reads_the_notification() -> None:
    recipient = _patient()
    row = _notification(recipient)

    response = get(f"/fhir/Communication/{row.pk}", token_of(recipient))

    body = response.json()
    assert response.status_code == 200
    assert body["resourceType"] == "Communication"
    assert body["recipient"] == [{"reference": f"Patient/{recipient.pk}"}]
    assert body["category"][0]["coding"][0]["code"] == "WAITLIST_OFFERED"
    assert "A slot is free" in body["payload"][0]["contentString"]
    assert "received" not in body
    assert response["Cache-Control"] == "no-store"


def returns_403_and_empty_search_when_an_admin_reads_another_users_notification() -> None:
    row = _notification(_patient())
    admin = token_of(role="ADMIN")

    read = get(f"/fhir/Communication/{row.pk}", admin)
    search = get("/fhir/Communication", admin)

    assert read.status_code == 403
    assert search.json()["total"] == 0


def returns_only_own_notifications_when_searching_by_category() -> None:
    recipient = _patient()
    _notification(recipient)
    _notification(recipient, kind="APPOINTMENT_REMINDER")
    _notification(_patient())

    search = get("/fhir/Communication?category=WAITLIST_OFFERED", token_of(recipient))

    assert search.status_code == 200
    assert search.json()["total"] == 1


def returns_401_when_a_notification_is_read_without_token() -> None:
    row = _notification(_patient())

    assert get(f"/fhir/Communication/{row.pk}").status_code == 401


def returns_200_and_stamps_the_server_clock_when_recipient_sets_received() -> None:
    recipient = _patient()
    row = _notification(recipient)
    token = token_of(recipient)
    stored = get(f"/fhir/Communication/{row.pk}", token).json()

    response = send(
        "put",
        f"/fhir/Communication/{row.pk}",
        {**stored, "received": "2030-01-07T06:00:00Z"},
        token,
    )

    assert response.status_code == 200
    assert Notification.objects.get(pk=row.pk).read_at == NOW
    assert response.json()["received"].startswith("2030-01-07T06:00:00")


def returns_400_naming_payload_when_recipient_changes_the_text() -> None:
    recipient = _patient()
    row = _notification(recipient)
    token = token_of(recipient)
    stored = get(f"/fhir/Communication/{row.pk}", token).json()
    changed = {**stored, "payload": [{"contentString": "other"}]}

    response = send("put", f"/fhir/Communication/{row.pk}", changed, token)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Communication.payload"]
    assert Notification.objects.get(pk=row.pk).read_at is None


def returns_403_when_another_user_marks_the_notification_read() -> None:
    row = _notification(_patient())
    stored = get(f"/fhir/Communication/{row.pk}", token_of(row.recipient)).json()

    response = send("put", f"/fhir/Communication/{row.pk}", stored, token_of(role="ADMIN"))

    assert response.status_code == 403
    assert Notification.objects.get(pk=row.pk).read_at is None


def returns_412_when_if_match_is_stale() -> None:
    recipient = _patient()
    row = _notification(recipient)
    token = token_of(recipient)
    stored = get(f"/fhir/Communication/{row.pk}", token).json()

    response = send("put", f"/fhir/Communication/{row.pk}", stored, token, **{"If-Match": 'W/"99"'})

    assert response.status_code == 412


@pytest.mark.parametrize("method", ["post", "delete"])
def returns_405_when_a_communication_is_created_or_deleted(method: str) -> None:
    recipient = _patient()
    row = _notification(recipient)
    path = "/fhir/Communication" if method == "post" else f"/fhir/Communication/{row.pk}"

    response = send(method, path, {"resourceType": "Communication"}, token_of(recipient))

    assert response.status_code == 405


def _stored_and_token(row: Notification) -> tuple[dict[str, object], str]:
    token = token_of(row.recipient)
    return get(f"/fhir/Communication/{row.pk}", token).json(), token


def returns_title_and_body_joined_by_a_newline_and_title_alone_without_body() -> None:
    recipient = _patient()
    with_body = _notification(recipient)
    without_body = _notification(recipient, body="")
    token = token_of(recipient)

    first = get(f"/fhir/Communication/{with_body.pk}", token).json()
    second = get(f"/fhir/Communication/{without_body.pk}", token).json()

    assert first["payload"] == [{"contentString": "A slot is free\nTuesday 9:00"}]
    assert second["payload"] == [{"contentString": "A slot is free"}]


def returns_the_creation_time_as_sent() -> None:
    row = _notification(_patient())

    body = get(f"/fhir/Communication/{row.pk}", token_of(row.recipient)).json()

    assert datetime.fromisoformat(body["sent"]) == row.created_at.replace(
        microsecond=row.created_at.microsecond // 1000 * 1000
    )


def returns_practitioner_as_recipient_when_a_clinician_is_notified() -> None:
    clinician = make("User", role="CLINICIAN")
    assert isinstance(clinician, User)
    row = _notification(clinician)

    body = get(f"/fhir/Communication/{row.pk}", token_of(clinician)).json()

    assert body["recipient"] == [{"reference": f"Practitioner/{clinician.pk}"}]


def returns_about_the_waitlist_entry_when_the_notification_names_one() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))
    row = _notification(clinic.patient, waitlist_entry=entry)

    body = get(f"/fhir/Communication/{row.pk}", token_of(clinic.patient)).json()

    assert body["about"] == [{"reference": f"Appointment/{entry.pk}"}]


def returns_about_the_entry_id_when_the_appointment_came_from_a_waitlist_entry() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))
    send("post", "/fhir/AppointmentResponse", _accept(entry), token_of(clinic.patient))
    appointment = Appointment.objects.get(waitlist_entry=entry)
    row = _notification(clinic.patient, appointment=appointment)

    body = get(f"/fhir/Communication/{row.pk}", token_of(clinic.patient)).json()

    assert body["about"] == [{"reference": f"Appointment/{entry.pk}"}]


def returns_about_the_appointment_id_when_the_appointment_has_no_waitlist_entry() -> None:
    clinic = make_clinic()
    appointment = _booked_slot(clinic)
    row = _notification(clinic.patient, appointment=appointment)

    body = get(f"/fhir/Communication/{row.pk}", token_of(clinic.patient)).json()

    assert body["about"] == [{"reference": f"Appointment/{appointment.pk}"}]


def returns_no_about_when_the_notification_names_nothing() -> None:
    row = _notification(_patient())

    body = get(f"/fhir/Communication/{row.pk}", token_of(row.recipient)).json()

    assert "about" not in body


def returns_200_and_changes_nothing_when_the_unchanged_resource_is_put_back() -> None:
    row = _notification(_patient())
    stored, token = _stored_and_token(row)

    response = send("put", f"/fhir/Communication/{row.pk}", stored, token)

    assert response.status_code == 200
    assert Notification.objects.get(pk=row.pk).read_at is None


def returns_200_when_the_read_resource_is_put_back_with_its_received_time() -> None:
    row = _notification(_patient(), read_at=NOW)
    stored, token = _stored_and_token(row)

    response = send("put", f"/fhir/Communication/{row.pk}", stored, token)

    assert response.status_code == 200


def returns_400_naming_received_when_received_is_set_a_second_time() -> None:
    row = _notification(_patient(), read_at=NOW)
    stored, token = _stored_and_token(row)

    response = send(
        "put",
        f"/fhir/Communication/{row.pk}",
        {**stored, "received": "2031-02-02T00:00:00Z"},
        token,
    )

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Communication.received"]
    assert Notification.objects.get(pk=row.pk).read_at == NOW


@pytest.mark.parametrize("received", ["not a time", 12345])
def returns_400_naming_received_when_received_is_not_a_date_time(received: object) -> None:
    row = _notification(_patient())
    stored, token = _stored_and_token(row)

    response = send("put", f"/fhir/Communication/{row.pk}", {**stored, "received": received}, token)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Communication.received"]
    assert Notification.objects.get(pk=row.pk).read_at is None
