"""Task 17c: the clinician workspace defects of QA round 2, each as a browser meets it.
Fixtures are built here, never read from the demo seed."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.test import Client

from scheduling.models import Appointment, AuditLogEntry, Notification, TimeOff, User
from scheduling.models.builders import Clinic, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, signed_in_patient
from scheduling.views.pages.browser_support import browser_post

pytestmark = pytest.mark.django_db

BERLIN = ZoneInfo("Europe/Berlin")
COLUMN_MARKER = '<li class="time-grid__column">'
ITEMS_PATTERN = re.compile(r'<ol class="time-grid__items">(.*?)</ol>', re.S)
WEEK_PATH = "/clinician/calendar?week=2026-11-30"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _clinician_client(clinic: Clinic) -> Client:
    user = clinic.clinician.user
    assert isinstance(user, User)
    return signed_in_patient(user)


def _local(day: int, month: int, hour: int, minute: int = 0, year: int = 2026) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=BERLIN).astimezone(UTC)


def _time_off(clinic: Clinic, starts_at: datetime, ends_at: datetime, reason: str = "") -> TimeOff:
    row = make(
        "TimeOff", clinician=clinic.clinician, starts_at=starts_at, ends_at=ends_at, reason=reason
    )
    assert isinstance(row, TimeOff)
    return row


def _columns(html: str) -> list[str]:
    return html.split(COLUMN_MARKER)[1:]


def _inside(column: str) -> str:
    found = ITEMS_PATTERN.search(column)
    assert found is not None
    return found.group(1)


# --- #26 multi-day time off on the week grid ---


def returns_time_off_in_every_day_it_covers_when_period_spans_days() -> None:
    clinic = make_clinic()
    _time_off(clinic, _local(1, 12, 1), _local(4, 12, 1))

    html = _clinician_client(clinic).get(WEEK_PATH).content.decode()

    columns = _columns(html)
    assert "Time off" not in columns[0] and "Time off" not in columns[5]
    for tuesday_to_thursday in columns[1:4]:
        assert "time-grid-off" in _inside(tuesday_to_thursday)
    assert "time-grid-off" not in _inside(columns[4])
    assert "Fri 4 Dec 01:00" in columns[4]


def returns_whole_grid_rows_when_a_day_is_wholly_off() -> None:
    clinic = make_clinic()
    _time_off(clinic, _local(1, 12, 1), _local(4, 12, 1))

    html = _clinician_client(clinic).get(WEEK_PATH).content.decode()

    wednesday, thursday = _columns(html)[2], _columns(html)[3]
    for column in (wednesday, thursday):
        assert "time-grid-at-1 time-grid-span-24" in _inside(column)


def returns_real_start_and_end_with_dates_when_period_spans_days() -> None:
    clinic = make_clinic()
    _time_off(clinic, _local(1, 12, 1), _local(4, 12, 1))

    html = _clinician_client(clinic).get(WEEK_PATH).content.decode()

    wednesday = _inside(_columns(html)[2])
    assert "Tue 1 Dec 01:00 to Fri 4 Dec 01:00" in " ".join(wednesday.split())


def returns_first_day_to_the_end_of_the_grid_when_period_starts_before_seven() -> None:
    clinic = make_clinic()
    _time_off(clinic, _local(1, 12, 1), _local(4, 12, 1))

    html = _clinician_client(clinic).get(WEEK_PATH).content.decode()

    assert "time-grid-at-1 time-grid-span-24" in _inside(_columns(html)[1])


# --- #40 whole-day time off reads All day ---


def returns_all_day_label_when_time_off_covers_a_whole_day() -> None:
    clinic = make_clinic()
    _time_off(clinic, _local(30, 11, 0), _local(1, 12, 0))

    html = _clinician_client(clinic).get(WEEK_PATH).content.decode()

    assert "All day" in _inside(_columns(html)[0])
    assert "00:00 to 00:00" not in html


def returns_clock_span_when_time_off_starts_mid_day() -> None:
    clinic = make_clinic()
    _time_off(clinic, _local(30, 11, 10), _local(30, 11, 12))

    html = _clinician_client(clinic).get(WEEK_PATH).content.decode()

    assert "10:00 to 12:00" in _inside(_columns(html)[0])
    assert "All day" not in _inside(_columns(html)[0])


# --- #30 overlaps, long words and the empty last column ---


def returns_overlapping_blocks_in_one_column_with_their_rows_when_they_overlap() -> None:
    clinic = make_clinic()
    _time_off(clinic, _local(23, 11, 11), _local(23, 11, 13), "lunch")
    make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=_local(23, 11, 12),
        ends_at=_local(23, 11, 12, 30),
    )

    html = _clinician_client(clinic).get("/clinician/calendar?week=2026-11-23").content.decode()

    monday = _inside(_columns(html)[0])
    assert "time-grid-at-9 time-grid-span-4" in monday
    assert "time-grid-at-11 time-grid-span-1" in monday


def returns_reason_escaped_and_once_inside_its_block_when_reason_is_long_and_unbroken() -> None:
    clinic = make_clinic()
    long_reason = "x" * 200
    _time_off(clinic, _local(23, 11, 11), _local(23, 11, 13), "lunch <b>x</b>")
    _time_off(clinic, _local(24, 11, 11), _local(24, 11, 12), long_reason)

    html = _clinician_client(clinic).get("/clinician/calendar?week=2026-11-23").content.decode()

    assert "lunch &lt;b&gt;x&lt;/b&gt;" in html and "<b>x</b>" not in html
    assert html.count(long_reason) == 2  # the drawn line and the accessible name, in one block
    assert long_reason in _inside(_columns(html)[1])


def returns_empty_text_in_a_list_item_of_its_column_when_the_day_is_free() -> None:
    clinic = make_clinic()

    html = _clinician_client(clinic).get("/clinician/calendar?week=2026-11-23").content.decode()

    assert all('<li class="time-grid__none">' in _inside(column) for column in _columns(html))


def returns_same_grid_placement_on_rooms_when_time_off_runs_before_seven() -> None:
    clinic = make_clinic()
    room = make("Room", department=clinic.department)
    make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        room=room,
        starts_at=_local(23, 11, 12),
        ends_at=_local(23, 11, 12, 30),
    )

    html = _clinician_client(clinic).get("/clinician/rooms?date=2026-11-23").content.decode()

    assert "time-grid-at-11 time-grid-span-1" in html


# --- #31 ambiguous local time ---


def returns_303_and_first_occurrence_when_time_off_starts_in_the_repeated_hour() -> None:
    clinic = make_clinic()
    form = {"starts_at": "2026-10-25T02:30", "ends_at": "2026-10-25T04:30", "reason": ""}

    response = browser_post(_clinician_client(clinic), "/clinician/time-off", form)

    stored = TimeOff.objects.get(clinician=clinic.clinician)
    assert response.status_code == 303
    assert stored.starts_at == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert stored.ends_at == datetime(2026, 10, 25, 3, 30, tzinfo=UTC)


def returns_422_and_no_row_when_time_off_starts_in_the_skipped_hour() -> None:
    clinic = make_clinic()
    form = {"starts_at": "2026-03-29T02:30", "ends_at": "2026-03-29T04:30", "reason": ""}

    response = browser_post(_clinician_client(clinic), "/clinician/time-off", form)

    assert response.status_code == 422
    assert "exists in the hospital" in response.content.decode()
    assert not TimeOff.objects.filter(clinician=clinic.clinician).exists()


def returns_422_and_date_message_and_no_clock_sentence_when_time_off_names_30_february() -> None:
    clinic = make_clinic()
    form = {"starts_at": "2027-02-30T10:00", "ends_at": "2027-02-30T11:00", "reason": "x"}

    response = browser_post(_clinician_client(clinic), "/clinician/time-off", form)

    body = response.content.decode()
    assert response.status_code == 422
    assert "That date does not exist" in body
    assert "clocks skip" not in body
    assert not TimeOff.objects.filter(clinician=clinic.clinician).exists()


@pytest.mark.parametrize("year", ["0001", "9999", "10000"])
def returns_422_and_date_message_when_time_off_year_is_outside_the_window(year: str) -> None:
    clinic = make_clinic()
    form = {"starts_at": f"{year}-01-01T10:00", "ends_at": f"{year}-01-01T11:00", "reason": "x"}

    response = browser_post(_clinician_client(clinic), "/clinician/time-off", form)

    body = response.content.decode()
    assert response.status_code == 422
    assert "That date does not exist" in body
    assert "clocks skip" not in body
    assert not TimeOff.objects.filter(clinician=clinic.clinician).exists()


def returns_422_and_clock_message_when_time_off_start_is_left_empty() -> None:
    clinic = make_clinic()
    form = {"starts_at": "", "ends_at": "2027-02-01T11:00", "reason": "x"}

    response = browser_post(_clinician_client(clinic), "/clinician/time-off", form)

    body = response.content.decode()
    assert response.status_code == 422
    assert "exists in the hospital" in body
    assert "That date does not exist" not in body
    assert not TimeOff.objects.filter(clinician=clinic.clinician).exists()


def returns_rule_beside_the_fields_when_time_off_page_opens() -> None:
    html = _clinician_client(make_clinic()).get("/clinician/time-off").content.decode()

    assert "When clocks go back, an hour happens twice; the first one is used." in html


# --- #28 unique ids ---


def returns_label_bound_to_its_own_form_when_time_off_page_renders() -> None:
    html = _clinician_client(make_clinic()).get("/clinician/time-off").content.decode()

    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    record_form = html.split('id="record-title"')[1]
    for field in ("starts_at", "ends_at"):
        label_for = re.search(
            rf'<label[^>]*for="([^"]+)"[^>]*>{"From" if field == "starts_at" else "To"}<',
            record_form,
        )
        assert label_for is not None
        assert f'id="{label_for.group(1)}"' in record_form


# --- #29 reschedule refusals ---


def _booked(clinic: Clinic) -> Appointment:
    row = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=NOW + timedelta(days=7, hours=4),
        ends_at=NOW + timedelta(days=7, hours=4, minutes=30),
    )
    assert isinstance(row, Appointment)
    return row


@pytest.mark.parametrize(
    ("asked", "reason"),
    [
        ("2020-01-01T10:00:00Z", "That time has already passed."),
        ("9999-12-31T10:00:00Z", "That time is not offered. Choose one from the week."),
        ("2099-12-31T10:00:00Z", "That time is not offered. Choose one from the week."),
    ],
)
def returns_422_naming_the_reason_and_the_week_when_clinician_reschedules_to_a_bad_time(
    asked: str, reason: str
) -> None:
    clinic = make_clinic()
    appointment = _booked(clinic)
    base = f"/clinician/appointments/{appointment.pk}/reschedule"

    response = browser_post(_clinician_client(clinic), f"{base}/review?starts_at={asked}", {})

    html = response.content.decode()
    assert response.status_code == 422
    assert reason in html and "just taken" not in html
    assert f'href="{base}"' in html


@pytest.mark.parametrize(
    ("asked", "reason"),
    [
        ("2020-01-01T10:00:00Z", "That time has already passed."),
        ("9999-12-31T10:00:00Z", "That time is not offered. Choose one from the week."),
        ("2099-12-31T10:00:00Z", "That time is not offered. Choose one from the week."),
    ],
)
def returns_422_naming_the_reason_and_the_week_when_patient_reschedules_to_a_bad_time(
    asked: str, reason: str
) -> None:
    clinic = make_clinic()
    appointment = _booked(clinic)
    base = f"/patient/appointments/{appointment.pk}/reschedule"

    response = browser_post(
        signed_in_patient(clinic.patient), f"{base}/review?starts_at={asked}", {}
    )

    html = response.content.decode()
    assert response.status_code == 422
    assert reason in html and "just taken" not in html
    assert f'href="{base}"' in html


# --- #27 history in plain words ---


def returns_booked_in_the_history_when_the_book_action_was_audited() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic)
    make(
        "AuditLogEntry",
        action="appointment.book",
        entity_type="Appointment",
        entity_id=str(appointment.pk),
        actor=clinic.patient,
    )

    html = (
        _clinician_client(clinic).get(f"/clinician/appointments/{appointment.pk}").content.decode()
    )

    assert "appointment.book" not in html


# --- #39 reschedule to the current start ---


def returns_303_without_audit_or_notification_when_clinician_review_posts_current_start() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic)
    review = f"/clinician/appointments/{appointment.pk}/reschedule/review"

    response = browser_post(
        _clinician_client(clinic), f"{review}?starts_at=2030-01-14T10:00:00Z", {}
    )

    assert response.status_code == 303
    assert AuditLogEntry.objects.filter(action="appointment.reschedule").count() == 0
    assert (
        Notification.objects.filter(appointment=appointment, kind="SCHEDULE_CHANGED").count() == 0
    )
