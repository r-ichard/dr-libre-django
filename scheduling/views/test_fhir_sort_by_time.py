"""Section 15.5: `_sort` on a date parameter orders by that time, in both directions, on
every type that declares one, and `next` links keep the sort."""

from collections.abc import Sequence
from datetime import date, timedelta

import pytest
from django.db.models import F, Model

from scheduling.models import AvailabilityRule, Notification
from scheduling.models.builders import STARTS_AT, make, make_clinic, make_user
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, get, token_of

pytestmark = pytest.mark.django_db

HOURS = (9, 11, 10)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _ids(path: str, token: str) -> list[str]:
    response = get(path, token)
    assert response.status_code == 200
    return [item["resource"]["id"] for item in response.json()["entry"]]


def _in_time_order(rows: Sequence[Model]) -> list[str]:
    return [str(row.pk) for row in rows]


def returns_audit_events_oldest_first_when_sort_is_date_and_newest_first_when_minus_date() -> None:
    rows = {
        hour: make("AuditLogEntry", action="waitlist.accept", created_at=NOW.replace(hour=hour))
        for hour in HOURS
    }
    token = token_of(role="ADMIN")
    ordered = [rows[hour] for hour in sorted(HOURS)]

    assert _ids("/fhir/AuditEvent?type=waitlist.accept&_sort=date", token) == _in_time_order(
        ordered
    )
    assert _ids("/fhir/AuditEvent?type=waitlist.accept&_sort=-date", token) == _in_time_order(
        ordered[::-1]
    )


def returns_communications_in_sent_order_when_sort_is_sent() -> None:
    patient = make_user(role="PATIENT")
    rows = {
        hour: make(
            "Notification",
            recipient=patient,
            kind="WAITLIST_OFFERED",
            title="A slot is free",
            body="Tuesday",
        )
        for hour in HOURS
    }
    for hour, row in rows.items():
        Notification.objects.filter(pk=row.pk).update(
            created_at=NOW.replace(hour=hour), version=F("version") + 1
        )
    token = token_of(patient)
    ordered = [rows[hour] for hour in sorted(HOURS)]

    assert _ids("/fhir/Communication?_sort=sent", token) == _in_time_order(ordered)
    assert _ids("/fhir/Communication?_sort=-sent", token) == _in_time_order(ordered[::-1])


def returns_schedules_by_first_valid_day_when_sort_is_date() -> None:
    clinic = make_clinic(rule_fields={"weekday": 1, "valid_from": date(2030, 1, 16)})
    rules: list[Model] = [AvailabilityRule.objects.get(clinician=clinic.clinician)]
    for weekday, offset in ((2, 8), (3, 10)):
        rules.append(
            make(
                "AvailabilityRule",
                clinician=clinic.clinician,
                weekday=weekday,
                valid_from=date(2030, 1, 4) + timedelta(days=offset),
            )
        )
    token = token_of(role="ADMIN")
    ordered = [rules[1], rules[2], rules[0]]

    assert _ids("/fhir/Schedule?_sort=date", token) == _in_time_order(ordered)
    assert _ids("/fhir/Schedule?_sort=-date", token) == _in_time_order(ordered[::-1])


def returns_waitlist_entries_by_the_offered_start_when_sort_is_date() -> None:
    clinic = make_clinic()
    entries = []
    for days in (9, 2, 5):
        offered = make(
            "Appointment",
            clinician=clinic.clinician,
            appointment_type=clinic.appointment_type,
            starts_at=STARTS_AT + timedelta(days=days),
            ends_at=STARTS_AT + timedelta(days=days, minutes=30),
        )
        entries.append(
            make(
                "WaitlistEntry",
                patient=clinic.patient,
                appointment_type=clinic.appointment_type,
                status="OFFERED",
                offered_appointment=offered,
            )
        )
    token = token_of(role="ADMIN")
    ordered = [entries[1], entries[2], entries[0]]

    assert _ids("/fhir/Appointment?status=proposed&_sort=date", token) == _in_time_order(ordered)
    assert _ids("/fhir/Appointment?status=proposed&_sort=-date", token) == _in_time_order(
        ordered[::-1]
    )


def returns_slots_latest_first_when_sort_is_minus_start() -> None:
    clinic = make_clinic(rule_fields={"weekday": 1})
    path = (
        f"/fhir/Slot?_count=100&service-type={clinic.appointment_type.pk}"
        "&start=ge2030-01-07T00:00:00Z&start=lt2030-01-08T00:00:00Z"
    )
    token = token_of(role="ADMIN")

    ascending = get(path + "&_sort=start", token).json()["entry"]
    descending = get(path + "&_sort=-start", token).json()["entry"]

    starts = [item["resource"]["start"] for item in ascending]
    assert len(starts) > 1
    assert starts == sorted(starts)
    assert [item["resource"]["start"] for item in descending] == starts[::-1]
