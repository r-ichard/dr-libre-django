"""Task 21, items 4 to 7 and 13: the admin dashboard as a browser uses it. Route:
/admin-console/?range=today|7|30. NOW is 2030-01-07 06:00 UTC, a Monday, at a UTC hospital."""

import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from itertools import count

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.models import Appointment, WaitlistEntry
from scheduling.models.builders import Clinic, add_clinician, make, make_clinic, make_user
from scheduling.views import clock
from scheduling.views.pages.admin_support import admin_client

pytestmark = pytest.mark.django_db

SLOTS = count()
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
PATH = "/admin-console/"
ANY_QUERY_BOUND = 12
TILE_PATTERN = re.compile(r'stat-tile__label">([^<]*?) </p><p class="stat-tile__value">([^<]*)</p>')


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _tiles(html: str) -> dict[str, str]:
    return dict(TILE_PATTERN.findall(html))


def _book(
    clinic: Clinic, days_ago: int = 0, status: str = "BOOKED", source: str = "ONLINE"
) -> Appointment:
    starts_at = NOW - timedelta(days=days_ago, hours=1, minutes=40 * next(SLOTS))
    cancelled = {"cancelled_at": NOW, "cancellation_reason": "x"} if status == "CANCELLED" else {}
    appointment = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        status=status,
        source=source,
        **cancelled,
    )
    assert isinstance(appointment, Appointment)
    return appointment


def returns_zeros_and_n_a_when_no_appointment_exists() -> None:
    response = admin_client().get(PATH)

    tiles = _tiles(response.content.decode())
    assert response.status_code == 200
    assert tiles["Appointments"] == "0"
    assert tiles["Cancellations"] == "0"
    assert tiles["Waitlist size"] == "0"
    assert [tiles[name] for name in ("Utilisation", "No-show rate", "Online share")] == ["n/a"] * 3


def returns_the_rule_for_days_and_today_on_the_page() -> None:
    html = admin_client().get(PATH).content.decode()

    assert "Days are days on each hospital" in html
    assert "Today is the latest date at any hospital" in html


def returns_tiles_equal_to_the_database_when_appointments_exist() -> None:
    clinic = make_clinic()
    _book(clinic, 0)
    _book(clinic, 1, source="STAFF")
    _book(clinic, 2, status="NO_SHOW")
    _book(clinic, 3, status="CANCELLED")
    make("WaitlistEntry", patient=clinic.patient, appointment_type=clinic.appointment_type,
         earliest_at=NOW, latest_at=NOW + timedelta(days=3), status="WAITING")  # fmt: skip

    tiles = _tiles(admin_client().get(PATH).content.decode())

    assert tiles["Appointments"] == "3"
    assert tiles["Cancellations"] == "1"
    assert tiles["No-show rate"] == "33 %"
    assert tiles["Online share"] == "67 %"
    assert tiles["Waitlist size"] == str(WaitlistEntry.objects.count())


def returns_seven_days_when_the_range_is_missing_or_hostile() -> None:
    clinic = make_clinic()
    _book(clinic, 20)
    for asked in ("", "90", "7;", "=cmd", "٧", "<script>"):
        html = admin_client().get(PATH, {"range": asked}).content.decode()

        assert len(re.findall(r"<tr>\s*<th scope=\"row\">", html)) == 7, asked
        assert _tiles(html)["Appointments"] == "0"


def returns_the_asked_number_of_days_when_the_range_is_today_or_30() -> None:
    clinic = make_clinic()
    _book(clinic, 20)

    today = admin_client().get(PATH, {"range": "today"}).content.decode()
    month = admin_client().get(PATH, {"range": "30"}).content.decode()

    assert len(re.findall(r"<tr>\s*<th scope=\"row\">", today)) == 1
    assert len(re.findall(r"<tr>\s*<th scope=\"row\">", month)) == 30
    assert _tiles(month)["Appointments"] == "1"


def returns_the_five_busiest_clinicians_when_more_have_appointments() -> None:
    clinic = make_clinic()
    for index in range(6):
        other = add_clinician(clinic.department)
        for _ in range(index + 1):
            _book(Clinic(clinic.department, clinic.appointment_type, other, clinic.patient))

    html = admin_client().get(PATH).content.decode()

    assert len(re.findall(r"<li>[^<]*: \d+ appointments?</li>", html)) == 5
    assert ": 6 appointments" in html and ": 1 appointment<" not in html


def returns_a_table_with_the_total_of_the_tile_and_a_chart_without_script_or_style() -> None:
    clinic = make_clinic()
    for days_ago in (0, 0, 1):
        _book(clinic, days_ago)

    html = admin_client().get(PATH).content.decode()

    counts = re.findall(r'<td class="numeric">(\d+)</td>', html)
    assert sum(map(int, counts)) == int(_tiles(html)["Appointments"]) == 3
    assert "style=" not in html and "<script" not in html
    assert 'class="bar__value" x="0" y="0" width="100"' in html


def returns_no_duplicate_id_when_the_dashboard_is_filled() -> None:
    clinic = make_clinic()
    _book(clinic)

    html = admin_client().get(PATH).content.decode()

    ids = re.findall(r"""\sid=["']([^"']*)["']""", html)
    assert [name for name, count in Counter(ids).items() if count > 1] == []


def returns_the_same_number_of_queries_for_two_and_for_forty_appointments() -> None:
    clinic = make_clinic()
    for _ in range(2):
        _book(clinic)
    admin = admin_client()
    admin.get(PATH)
    with CaptureQueriesContext(connection) as few:
        admin.get(PATH)
    for _ in range(38):
        _book(clinic)
    with CaptureQueriesContext(connection) as many:
        admin.get(PATH)

    assert len(few) == len(many) <= ANY_QUERY_BOUND


def returns_forbidden_to_a_patient() -> None:
    make_user()
    from scheduling.views.pages.admin_support import client_of_role

    assert client_of_role("PATIENT").get(PATH).status_code == 403
