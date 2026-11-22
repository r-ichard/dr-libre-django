"""Task 20, item 11: the booking policy as the rules read it, and the reminder button."""

from datetime import UTC, datetime, timedelta

import pytest

from scheduling.domain import booking_rules
from scheduling.models import Notification
from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.pages.admin_support import admin_client, admin_post

pytestmark = pytest.mark.django_db

PATH = "/admin-console/settings"
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def returns_the_three_policy_values_when_the_settings_are_opened() -> None:
    response = admin_client().get(PATH)

    html = response.content.decode()
    assert response.status_code == 200
    assert "120" in html and "24" in html and "3" in html
    assert "no-store" in response["Cache-Control"]


def returns_the_changed_value_when_the_rules_constant_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(booking_rules, "LEAD_TIME", timedelta(minutes=45))

    html = admin_client().get(PATH).content.decode()

    assert "45" in html and "120" not in html


def returns_the_count_of_reminders_created_and_then_zero_when_the_button_is_pressed_twice() -> None:
    soon = NOW + timedelta(hours=20)
    make("Appointment", starts_at=soon, ends_at=soon + timedelta(minutes=30))
    client = admin_client()

    first = admin_post(client, f"{PATH}/reminders", {})
    shown_first = client.get(first["Location"]).content.decode()
    second = admin_post(client, f"{PATH}/reminders", {})
    shown_second = client.get(second["Location"]).content.decode()

    assert first.status_code == 303 and "1 reminder created" in shown_first
    assert "0 reminders created" in shown_second
    assert Notification.objects.filter(kind="APPOINTMENT_REMINDER").count() == 1


def returns_405_when_the_reminder_route_is_opened_with_get() -> None:
    assert admin_client().get(f"{PATH}/reminders").status_code == 405
