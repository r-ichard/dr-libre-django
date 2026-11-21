"""Task 15: the notification list, mark as read and the unread count, as a browser sends them."""

from __future__ import annotations

from datetime import timedelta

import pytest

from scheduling.models import AuditLogEntry, Notification, User
from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, no_inline_code, signed_in_patient
from scheduling.views.pages.browser_support import OTHER_SITE_ORIGIN, browser_post

pytestmark = pytest.mark.django_db

PATH = "/patient/notifications"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _notification(
    recipient: User, title: str, age_hours: int = 1, **fields: object
) -> Notification:
    row = make(
        "Notification",
        recipient=recipient,
        title=title,
        created_at=NOW - timedelta(hours=age_hours),
        **fields,
    )
    assert isinstance(row, Notification)
    return row


def _patient() -> User:
    patient = make("User")
    assert isinstance(patient, User)
    return patient


def returns_newest_first_with_unread_word_only_on_unread_rows() -> None:
    patient = _patient()
    _notification(patient, "Older note", 5, read_at=NOW)
    _notification(patient, "Newer note", 1)

    html = signed_in_patient(patient).get(PATH).content.decode()

    assert html.index("Newer note") < html.index("Older note")
    assert html.count("Unread</span>") == 1


def returns_ten_per_page_and_page_one_when_page_is_not_a_number() -> None:
    patient = _patient()
    for number in range(12):
        _notification(patient, f"Note {number:02d}", number + 1)

    client = signed_in_patient(patient)

    assert "Note 11" not in client.get(PATH).content.decode()
    assert "Note 11" in client.get(f"{PATH}?page=2").content.decode()
    assert "Note 00" in client.get(f"{PATH}?page=abc").content.decode()


def returns_empty_state_when_patient_has_no_notification() -> None:
    html = signed_in_patient(_patient()).get(PATH).content.decode()

    assert "No notifications" in html
    assert no_inline_code(html)


def returns_303_and_marks_read_when_mark_as_read_is_posted_as_a_browser_sends_it() -> None:
    patient = _patient()
    row = _notification(patient, "Mark me")

    response = browser_post(signed_in_patient(patient), f"{PATH}/{row.pk}/read", {})

    row.refresh_from_db()
    assert response.status_code == 303
    assert row.read_at == NOW
    assert AuditLogEntry.objects.filter(action="notification.read").count() == 1


def returns_403_when_mark_as_read_comes_from_another_site() -> None:
    patient = _patient()
    row = _notification(patient, "Mark me")

    response = browser_post(
        signed_in_patient(patient), f"{PATH}/{row.pk}/read", {}, OTHER_SITE_ORIGIN
    )

    row.refresh_from_db()
    assert response.status_code == 403
    assert row.read_at is None


def returns_403_and_leaves_row_unread_when_marking_another_patients_notification() -> None:
    patient = _patient()
    foreign = _notification(_patient(), "Foreign secret title")

    response = browser_post(signed_in_patient(patient), f"{PATH}/{foreign.pk}/read", {})

    foreign.refresh_from_db()
    assert response.status_code == 403
    assert "Foreign secret title" not in response.content.decode()
    assert foreign.read_at is None


def returns_404_when_marking_an_unknown_notification() -> None:
    response = browser_post(
        signed_in_patient(_patient()), f"{PATH}/00000000-0000-4000-8000-000000000000/read", {}
    )

    assert response.status_code == 404


def returns_303_and_marks_only_own_rows_when_mark_all_is_posted() -> None:
    patient = _patient()
    own = _notification(patient, "Own")
    foreign = _notification(_patient(), "Foreign")

    response = browser_post(signed_in_patient(patient), f"{PATH}/read-all", {})

    own.refresh_from_db()
    foreign.refresh_from_db()
    assert response.status_code == 303
    assert own.read_at == NOW
    assert foreign.read_at is None


def returns_unread_count_linked_to_the_list_on_the_home_page() -> None:
    patient = _patient()
    _notification(patient, "One")
    _notification(patient, "Two")

    html = signed_in_patient(patient).get("/patient/").content.decode()

    assert f'<a href="{PATH}">2 unread notifications</a>' in html
