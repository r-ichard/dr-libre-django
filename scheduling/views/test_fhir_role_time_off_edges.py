"""Task 24c: edges of a clinician's notAvailable write. Expected values come from spec 15.4 and
the console: a stored period is only repeated, never edited, and one clinician's time off is
never recorded on another's profile."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from scheduling.models import ClinicianProfile, TimeOff
from scheduling.models.builders import STARTS_AT, add_clinician, make
from scheduling.views import clock
from scheduling.views.fhir_role_support import element_names, period, stored_role
from scheduling.views.fhir_test_support import NOW, get, send, token_of

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db
DAY = timedelta(days=1)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _put(profile: ClinicianProfile, body: object, token: str) -> "_MonkeyPatchedWSGIResponse":
    return send("put", f"/fhir/PractitionerRole/{profile.pk}", body, token)


def _own() -> tuple[ClinicianProfile, str]:
    profile = add_clinician(make("Department"))
    return profile, token_of(profile.user)


def _entries(body: dict[str, object]) -> list[dict[str, object]]:
    entries = body["notAvailable"]
    assert isinstance(entries, list)  # noqa: S101
    return entries


def returns_403_and_records_nothing_when_a_clinician_with_a_profile_puts_another_role() -> None:
    victim = add_clinician(make("Department"))
    intruder, intruder_token = _own()
    body = stored_role(token_of(victim.user), victim)
    body["notAvailable"] = [period(STARTS_AT, STARTS_AT + DAY)]

    response = _put(victim, body, intruder_token)

    assert response.status_code == 403
    assert TimeOff.objects.count() == 0
    assert not TimeOff.objects.filter(clinician=intruder).exists()


def returns_400_when_a_stored_period_keeps_its_hours_but_changes_its_description() -> None:
    profile, token = _own()
    row = make("TimeOff", clinician=profile, reason="Congress")
    body = stored_role(token, profile)
    _entries(body)[0]["description"] = "Holiday"

    response = _put(profile, body, token)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.notAvailable[0]"]
    assert TimeOff.objects.get(pk=row.pk).reason == "Congress"


def returns_400_when_the_same_stored_id_is_sent_twice() -> None:
    profile, token = _own()
    make("TimeOff", clinician=profile)
    body = stored_role(token, profile)
    body["notAvailable"] = _entries(body) * 2

    response = _put(profile, body, token)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.notAvailable[1]"]


def returns_400_when_a_new_period_has_no_time_zone() -> None:
    profile, token = _own()
    body = stored_role(token, profile)
    body["notAvailable"] = [
        {"during": {"start": "2030-01-01T09:00:00", "end": "2030-01-01T17:00:00"}}
    ]

    response = _put(profile, body, token)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.notAvailable[0]"]
    assert TimeOff.objects.count() == 0


def returns_400_and_keeps_the_removed_period_when_a_new_period_in_the_same_put_is_refused() -> None:
    profile, token = _own()
    row = make("TimeOff", clinician=profile)
    body = stored_role(token, profile)
    body["notAvailable"] = [period(STARTS_AT + DAY, STARTS_AT)]

    response = _put(profile, body, token)

    assert response.status_code == 400
    assert TimeOff.objects.filter(pk=row.pk).exists()


def returns_notavailable_in_start_order_with_a_default_description() -> None:
    profile, token = _own()
    make("TimeOff", clinician=profile, starts_at=STARTS_AT + 3 * DAY, ends_at=STARTS_AT + 4 * DAY)
    make("TimeOff", clinician=profile, starts_at=STARTS_AT + DAY, ends_at=STARTS_AT + 2 * DAY)

    listed = _entries(stored_role(token, profile))

    starts = [str(entry["during"]) for entry in listed]
    assert starts == sorted(starts)
    assert {entry["description"] for entry in listed} == {"Time off"}


def returns_no_notavailable_when_a_visitor_reads_a_role_with_time_off() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    profile = add_clinician(department)
    make("TimeOff", clinician=profile)
    staff_view = stored_role(token_of(role="ADMIN"), profile)

    response = get(f"/fhir/PractitionerRole/{profile.pk}")

    assert response.status_code == 200
    assert "notAvailable" in staff_view
    assert "notAvailable" not in response.json()
