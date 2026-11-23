"""Task 14: ordering, paging, wording and the reschedule steps of the patient portal, as a browser
sends them. Each test states the behaviour in words, not the shape of the code."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from scheduling.models import Appointment
from scheduling.models.builders import STARTS_AT, Clinic, add_clinician, make, make_clinic
from scheduling.views import clock
from scheduling.views.booking_schemas import CANCELLATION_REASON_MAXIMUM
from scheduling.views.pages.booking_pages_support import NOW, signed_in_patient
from scheduling.views.pages.browser_support import browser_post

pytestmark = pytest.mark.django_db

LIST_PATH = "/patient/appointments"
IN_A_WEEK = STARTS_AT + timedelta(days=7)
IN_TWO_WEEKS = STARTS_AT + timedelta(days=14)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _booked(clinic: Clinic, starts_at: datetime, reason: str, **overrides: object) -> Appointment:
    fields = {
        "patient": clinic.patient,
        "clinician": clinic.clinician,
        "appointment_type": clinic.appointment_type,
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(minutes=30),
        "patient_reason": reason,
        **overrides,
    }
    appointment = make("Appointment", **fields)
    assert isinstance(appointment, Appointment)
    return appointment


def _positions(html: str, *markers: str) -> list[int]:
    return [html.index(marker) for marker in markers]


def returns_upcoming_soonest_first_and_past_latest_first() -> None:
    clinic = make_clinic()
    _booked(clinic, IN_TWO_WEEKS, "Upcoming later")
    _booked(clinic, IN_A_WEEK, "Upcoming sooner")
    _booked(clinic, NOW - timedelta(days=9), "Past older", status="COMPLETED")
    _booked(clinic, NOW - timedelta(days=2), "Past newer", status="COMPLETED")

    html = signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()

    sooner, later = _positions(html, "Upcoming sooner", "Upcoming later")
    newer, older = _positions(html, "Past newer", "Past older")
    assert sooner < later < html.index("Past appointments")
    assert newer < older


def returns_ten_past_rows_per_page_with_links_between_pages() -> None:
    clinic = make_clinic()
    for day in range(1, 12):
        _booked(clinic, NOW - timedelta(days=day), f"Past {day:02d}", status="COMPLETED")
    client = signed_in_patient(clinic.patient)

    first = client.get(LIST_PATH).content.decode()
    second = client.get(f"{LIST_PATH}?page=2").content.decode()

    assert "Past 01" in first and "Past 10" in first and "Past 11" not in first
    assert f"{LIST_PATH}?page=2" in first and f"{LIST_PATH}?page=0" not in first
    assert "Past 11" in second and "Past 01" not in second
    assert f"{LIST_PATH}?page=1" in second and f"{LIST_PATH}?page=3" not in second


@pytest.mark.parametrize("raw", ["abc", "-3", "0", "1" * 7])
def returns_first_page_when_page_number_is_unusable(raw: str) -> None:
    clinic = make_clinic()
    _booked(clinic, NOW - timedelta(days=1), "Past only", status="COMPLETED")

    html = signed_in_patient(clinic.patient).get(f"{LIST_PATH}?page={raw}").content.decode()

    assert "Past only" in html


def returns_room_name_only_when_a_room_is_assigned() -> None:
    clinic = make_clinic()
    room = make("Room", department=clinic.department, name="Room 7B")
    _booked(clinic, IN_A_WEEK, "With room", room=room)
    _booked(clinic, IN_TWO_WEEKS, "No room")
    html = signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()

    with_room, without_room = html.split("No room")[0], html.split("No room")[1]

    assert "Room 7B" in with_room
    assert "Room 7B" not in without_room


def returns_calendar_link_only_when_not_cancelled() -> None:
    clinic = make_clinic()
    cancelled = _booked(
        clinic, IN_A_WEEK, "Gone", status="CANCELLED", cancelled_at=NOW, cancellation_reason="Away"
    )

    html = signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()

    assert f"/appointments/{cancelled.pk}/calendar.ics" not in html


def returns_required_message_when_cancel_reason_is_blank() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, IN_A_WEEK, "Knee")

    response = browser_post(
        signed_in_patient(clinic.patient), f"{LIST_PATH}/{appointment.pk}/cancel", {"reason": "  "}
    )

    html = response.content.decode()
    assert response.status_code == 422
    assert "Enter a reason for cancelling." in html
    assert 'href="#id_reason"' in html


def returns_too_long_message_and_keeps_booking_when_cancel_reason_is_over_the_limit() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, IN_A_WEEK, "Knee")
    reason = "x" * (CANCELLATION_REASON_MAXIMUM + 1)

    response = browser_post(
        signed_in_patient(clinic.patient),
        f"{LIST_PATH}/{appointment.pk}/cancel",
        {"reason": reason},
    )

    appointment.refresh_from_db()
    assert response.status_code == 422
    assert "Keep the reason under" in response.content.decode()
    assert appointment.status == "BOOKED"


@pytest.mark.parametrize("step", ["cancel", "reschedule"])
def returns_409_with_reason_and_phone_when_form_is_asked_for_inside_24_hours(step: str) -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, STARTS_AT, "Soon")

    response = signed_in_patient(clinic.patient).get(f"{LIST_PATH}/{appointment.pk}/{step}")

    html = response.content.decode()
    assert response.status_code == 409
    assert "less than 24 hours" in html and "+49 30 1234" in html
    assert "<form" not in html.replace('<form method="post" action="/sign-out"', "")


def returns_409_without_changing_when_reschedule_is_asked_for_a_checked_in_appointment() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, IN_A_WEEK, "Here", status="CHECKED_IN")

    response = signed_in_patient(clinic.patient).get(f"{LIST_PATH}/{appointment.pk}/reschedule")

    assert response.status_code == 409
    assert "already checked in" in response.content.decode()


def returns_week_of_slots_linking_to_review_when_rescheduling() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, IN_A_WEEK, "Knee")

    response = signed_in_patient(clinic.patient).get(
        f"{LIST_PATH}/{appointment.pk}/reschedule?week=2030-01-21"
    )

    html = response.content.decode()
    assert response.status_code == 200
    assert f"{LIST_PATH}/{appointment.pk}/reschedule/review?starts_at=2030-01-21T10:00:00Z" in html


def returns_week_of_first_free_time_when_rescheduling_and_week_is_not_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Monday 14 January is the first free Monday; the strip's next link is the week after it.
    monkeypatch.setattr(clock, "now_utc", lambda: datetime(2030, 1, 13, 12, 0, tzinfo=UTC))
    clinic = make_clinic()
    appointment = _booked(clinic, IN_TWO_WEEKS, "Knee")

    response = signed_in_patient(clinic.patient).get(f"{LIST_PATH}/{appointment.pk}/reschedule")

    html = response.content.decode()
    assert response.status_code == 200
    assert "Mon 14 Jan" in html
    assert "week=2030-01-21" in html


def returns_old_and_new_time_on_review_and_404_without_a_start() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, IN_A_WEEK, "Knee")
    client = signed_in_patient(clinic.patient)
    review = f"{LIST_PATH}/{appointment.pk}/reschedule/review"

    shown = client.get(f"{review}?starts_at=2030-01-21T10:00:00Z")
    missing = client.get(review)

    html = shown.content.decode()
    assert shown.status_code == 200 and missing.status_code == 404
    assert "Monday 14 January 2030" in html and "Monday 21 January 2030" in html
    assert "Monday 14 January 2030, 11:00 to 11:30 (Europe/Berlin)" in html
    assert "Monday 21 January 2030, 11:00 to 11:30 (Europe/Berlin)" in html


def returns_303_and_moves_appointment_when_review_is_confirmed() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, IN_A_WEEK, "Knee")
    path = f"{LIST_PATH}/{appointment.pk}/reschedule/review?starts_at=2030-01-21T10:00:00Z"

    response = browser_post(signed_in_patient(clinic.patient), path, {})

    appointment.refresh_from_db()
    assert response.status_code == 303
    assert response["Location"] == LIST_PATH
    assert appointment.starts_at == IN_TWO_WEEKS


def returns_refusal_leading_to_times_when_the_slot_was_taken_meanwhile() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, IN_A_WEEK, "Knee")
    other = make_clinic()
    _booked(clinic, IN_TWO_WEEKS, "Taken", patient=other.patient)
    base = f"{LIST_PATH}/{appointment.pk}/reschedule"

    response = browser_post(
        signed_in_patient(clinic.patient), f"{base}/review?starts_at=2030-01-21T10:00:00Z", {}
    )

    appointment.refresh_from_db()
    assert response.status_code == 409
    assert f'href="{base}"' in response.content.decode()
    assert appointment.starts_at == IN_A_WEEK


def returns_403_without_moving_when_another_patient_posts_a_reschedule() -> None:
    clinic = make_clinic()
    other = make_clinic()
    foreign = _booked(other, IN_A_WEEK, "Not yours", patient=other.patient)
    path = f"{LIST_PATH}/{foreign.pk}/reschedule/review?starts_at=2030-01-21T10:00:00Z"

    response = browser_post(signed_in_patient(clinic.patient), path, {})

    foreign.refresh_from_db()
    assert response.status_code == 403
    assert foreign.starts_at == IN_A_WEEK


def returns_404_when_provider_step_names_an_unknown_type() -> None:
    clinic = make_clinic()
    unknown = "00000000-0000-4000-8000-000000000000"

    response = signed_in_patient(clinic.patient).get(f"/book/{unknown}/provider")

    assert response.status_code == 404


def returns_only_slots_of_the_same_provider_when_rescheduling() -> None:
    clinic = make_clinic()
    add_clinician(clinic.department)
    appointment = _booked(clinic, IN_A_WEEK, "Knee")
    other = make_clinic()
    _booked(clinic, IN_TWO_WEEKS, "Taken", patient=other.patient)

    html = (
        signed_in_patient(clinic.patient)
        .get(f"{LIST_PATH}/{appointment.pk}/reschedule?week=2030-01-21")
        .content.decode()
    )

    assert "starts_at=2030-01-21T10:00:00Z" not in html


def returns_first_available_link_without_provider_on_provider_step() -> None:
    clinic = make_clinic()

    html = (
        signed_in_patient(clinic.patient)
        .get(f"/book/{clinic.appointment_type.pk}/provider")
        .content.decode()
    )

    assert f'href="/book/{clinic.appointment_type.pk}"' in html


def returns_only_active_online_bookable_types_on_service_step() -> None:
    clinic = make_clinic(type_fields={"name": "Visible checkup"})
    make(
        "AppointmentType", department=clinic.department, name="Phone only", is_bookable_online=False
    )
    make("AppointmentType", department=clinic.department, name="Retired", is_active=False)

    html = signed_in_patient(clinic.patient).get("/book").content.decode()

    assert "Visible checkup" in html
    assert "Phone only" not in html and "Retired" not in html
