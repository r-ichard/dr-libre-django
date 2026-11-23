"""Section 7.1: the hold request names the field it was sent under, and a phone is
7 to 20 characters of digits, spaces and + ( ) - wherever it is typed (section 8)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from scheduling.models import BookingHold
from scheduling.models.builders import make_clinic
from scheduling.views import clock
from scheduling.views.test_booking_api import HOLDS, _body, _post

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _field_names(response: object) -> list[str]:
    error = response.json()["error"]  # type: ignore[attr-defined]
    return [item["field"] for item in error["details"]["fields"]]


def returns_date_of_birth_field_when_hold_has_an_impossible_birth_date() -> None:
    response = _post(HOLDS, _body(make_clinic(), date_of_birth="2999-01-01"))

    assert response.status_code == 400
    assert _field_names(response) == ["date_of_birth"]


@pytest.mark.parametrize("phone", ["abc", "12345", "1" * 21, "+49 30 12345x"])
def returns_phone_field_when_hold_has_a_phone_that_breaks_the_rule(phone: str) -> None:
    response = _post(HOLDS, _body(make_clinic(), phone=phone))

    assert response.status_code == 400
    assert _field_names(response) == ["phone"]
    assert BookingHold.objects.count() == 0


@pytest.mark.parametrize("phone", ["+49 (30) 123-456", "1234567", "1" * 20])
def returns_201_when_hold_has_a_phone_that_follows_the_rule(phone: str) -> None:
    response = _post(HOLDS, _body(make_clinic(), phone=phone))

    assert response.status_code == 201
