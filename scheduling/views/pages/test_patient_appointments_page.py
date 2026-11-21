"""Task 14: the patient's appointment lists, cancel step and ownership, as a browser sends them."""

from __future__ import annotations

from datetime import timedelta

import pytest

from scheduling.models import Appointment
from scheduling.models.builders import STARTS_AT, Clinic, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, no_inline_code, signed_in_patient
from scheduling.views.pages.browser_support import OTHER_SITE_ORIGIN, browser_post

pytestmark = pytest.mark.django_db

LIST_PATH = "/patient/appointments"
NEXT_WEEK = STARTS_AT + timedelta(days=7)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _appointment(clinic: Clinic, **overrides: object) -> Appointment:
    fields = {
        "patient": clinic.patient,
        "clinician": clinic.clinician,
        "appointment_type": clinic.appointment_type,
        "patient_reason": "Sore knee",
        **overrides,
    }
    appointment = make("Appointment", **fields)
    assert isinstance(appointment, Appointment)
    return appointment


def _later(clinic: Clinic, **overrides: object) -> Appointment:
    return _appointment(
        clinic, starts_at=NEXT_WEEK, ends_at=NEXT_WEEK + timedelta(minutes=30), **overrides
    )


def returns_row_with_whom_when_where_type_status_and_reason() -> None:
    clinic = make_clinic()
    _later(clinic)

    html = signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()

    assert "Monday 14 January 2030" in html
    assert "11:00" in html and "11:30" in html
    assert "Europe/Berlin" in html
    assert "Riverside Hospital" in html and "1 River Road" in html
    assert clinic.department.name in html
    assert clinic.appointment_type.name in html
    assert "Booked" in html
    assert "Sore knee" in html
    assert len([part for part in html.split("<h1") if part]) == 2
    assert no_inline_code(html)


def returns_cancel_and_reschedule_links_when_rules_allow() -> None:
    clinic = make_clinic()
    appointment = _later(clinic)

    html = signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()

    assert f"/patient/appointments/{appointment.pk}/cancel" in html
    assert f"/patient/appointments/{appointment.pk}/reschedule" in html
    assert f"/appointments/{appointment.pk}/calendar.ics" in html


def returns_reason_and_hospital_phone_instead_of_buttons_when_under_24_hours() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)

    html = signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()

    assert "less than 24 hours" in html
    assert "+49 30 1234" in html
    assert f"/patient/appointments/{appointment.pk}/cancel" not in html
    assert f"/patient/appointments/{appointment.pk}/reschedule" not in html


def returns_started_booked_appointment_as_past_without_cancel() -> None:
    clinic = make_clinic()
    started = _appointment(clinic, starts_at=NOW - timedelta(hours=1), ends_at=NOW)

    html = signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()

    upcoming_part, _, past_part = html.partition("Past appointments")
    assert clinic.appointment_type.name not in upcoming_part.split("Upcoming appointments")[-1]
    assert clinic.appointment_type.name in past_part
    assert f"/patient/appointments/{started.pk}/cancel" not in html


def returns_already_cancelled_wording_for_cancelled_row() -> None:
    clinic = make_clinic()
    _later(clinic, status="CANCELLED", cancellation_reason="Changed my mind", cancelled_at=NOW)

    html = signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()

    assert "already cancelled" in html
    assert "Cancelled" in html


def returns_only_own_appointments() -> None:
    clinic = make_clinic()
    other = make_clinic()
    _later(clinic, patient_reason="My own reason")
    _later(other, patient=other.patient, patient_reason="Stranger secret")

    html = signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()

    assert "My own reason" in html
    assert "Stranger secret" not in html


def returns_empty_states_with_actions_when_patient_has_no_appointments() -> None:
    clinic = make_clinic()

    html = signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()

    assert "No upcoming appointments" in html
    assert 'href="/book"' in html
    assert "No past appointments" in html


def returns_redirect_to_sign_in_when_anonymous() -> None:
    clinic = make_clinic()
    anonymous = signed_in_patient(clinic.patient)
    anonymous.cookies.clear()

    response = anonymous.get(LIST_PATH)

    assert response.status_code == 302
    assert response["Location"] == "/sign-in?next=/patient/appointments"


def returns_no_store_header_on_list() -> None:
    clinic = make_clinic()
    _later(clinic)

    response = signed_in_patient(clinic.patient).get(LIST_PATH)

    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]


def returns_404_when_cancel_id_is_unknown() -> None:
    clinic = make_clinic()
    unknown = "00000000-0000-4000-8000-000000000000"

    own = _later(clinic)
    client = signed_in_patient(clinic.patient)

    answers = [
        client.get(f"{LIST_PATH}/{appointment_id}/cancel") for appointment_id in (own.pk, unknown)
    ]

    assert [answer.status_code for answer in answers] == [200, 404]


def returns_403_without_the_appointment_when_it_belongs_to_another_patient() -> None:
    clinic = make_clinic()
    other = make_clinic()
    foreign = _later(other, patient=other.patient, patient_reason="Stranger secret")
    client = signed_in_patient(clinic.patient)

    pages = [client.get(f"{LIST_PATH}/{foreign.pk}/{step}") for step in ("cancel", "reschedule")]

    assert [page.status_code for page in pages] == [403, 403]
    assert all("Stranger secret" not in page.content.decode() for page in pages)


def returns_403_and_keeps_status_when_another_patient_posts_a_cancel() -> None:
    clinic = make_clinic()
    other = make_clinic()
    foreign = _later(other, patient=other.patient)

    response = browser_post(
        signed_in_patient(clinic.patient),
        f"{LIST_PATH}/{foreign.pk}/cancel",
        {"reason": "Not mine"},
    )

    foreign.refresh_from_db()
    assert response.status_code == 403
    assert foreign.status == "BOOKED"


def returns_422_with_error_summary_when_cancel_reason_is_empty() -> None:
    clinic = make_clinic()
    appointment = _later(clinic)

    response = browser_post(
        signed_in_patient(clinic.patient), f"{LIST_PATH}/{appointment.pk}/cancel", {"reason": ""}
    )

    appointment.refresh_from_db()
    assert response.status_code == 422
    assert (
        'role="alert"' in response.content.decode() or "error-summary" in response.content.decode()
    )
    assert appointment.status == "BOOKED"


def returns_303_and_cancels_with_reason_when_reason_is_given() -> None:
    clinic = make_clinic()
    appointment = _later(clinic)

    response = browser_post(
        signed_in_patient(clinic.patient),
        f"{LIST_PATH}/{appointment.pk}/cancel",
        {"reason": "Feeling better"},
    )

    appointment.refresh_from_db()
    assert response.status_code == 303
    assert response["Location"].startswith(LIST_PATH)
    assert appointment.status == "CANCELLED"
    assert appointment.cancellation_reason == "Feeling better"


def returns_refusal_page_with_way_forward_when_cancelling_twice() -> None:
    clinic = make_clinic()
    appointment = _later(clinic)
    client = signed_in_patient(clinic.patient)
    path = f"{LIST_PATH}/{appointment.pk}/cancel"
    browser_post(client, path, {"reason": "First"})

    second = browser_post(client, path, {"reason": "Second"})

    html = second.content.decode()
    assert second.status_code == 409
    assert "no longer allows" in html
    assert f'href="{LIST_PATH}"' in html


def returns_403_when_cancel_post_comes_from_another_origin() -> None:
    clinic = make_clinic()
    appointment = _later(clinic)

    response = browser_post(
        signed_in_patient(clinic.patient),
        f"{LIST_PATH}/{appointment.pk}/cancel",
        {"reason": "Cross site"},
        origin=OTHER_SITE_ORIGIN,
    )

    appointment.refresh_from_db()
    assert response.status_code == 403
    assert appointment.status == "BOOKED"


def returns_service_step_grouped_by_hospital_and_department() -> None:
    clinic = make_clinic()

    html = signed_in_patient(clinic.patient).get("/book").content.decode()

    assert "Riverside Hospital" in html
    assert clinic.department.name in html
    assert f"/book/{clinic.appointment_type.pk}/provider" in html
    assert no_inline_code(html)


def returns_provider_step_with_first_available_and_named_provider() -> None:
    clinic = make_clinic()

    html = (
        signed_in_patient(clinic.patient)
        .get(f"/book/{clinic.appointment_type.pk}/provider")
        .content.decode()
    )

    assert "First available" in html
    assert f"/book/{clinic.appointment_type.pk}?provider={clinic.clinician.pk}" in html


HOME_PATH = "/patient/"


def returns_home_with_next_appointment_unread_count_and_book_action() -> None:
    clinic = make_clinic()
    _later(clinic)
    day_after = NEXT_WEEK + timedelta(days=1)
    _appointment(clinic, starts_at=day_after, ends_at=day_after + timedelta(minutes=30))
    make("Notification", recipient=clinic.patient, read_at=None)
    make("Notification", recipient=clinic.patient, read_at=None)
    make("Notification", recipient=clinic.patient, read_at=NOW)
    make("Notification", recipient=make("User"), read_at=None)

    html = signed_in_patient(clinic.patient).get(HOME_PATH).content.decode()

    assert "Monday 14 January 2030" in html
    assert html.count('class="card appointment"') == 1
    assert "2 unread notifications" in html
    assert 'href="/book"' in html and "Book an appointment" in html
    assert no_inline_code(html)


def returns_home_empty_state_when_patient_has_no_upcoming_appointment() -> None:
    clinic = make_clinic()

    html = signed_in_patient(clinic.patient).get(HOME_PATH).content.decode()

    assert "No upcoming appointments" in html
    assert "0 unread notifications" in html
    assert 'href="/book"' in html
