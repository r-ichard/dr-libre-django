"""Task 24c: a clinician's token updates the own PractitionerRole.notAvailable and nothing else
(spec 15.4). Time off is recorded and removed, never edited."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from scheduling.models import AuditLogEntry, ClinicianProfile, TimeOff
from scheduling.models.builders import STARTS_AT, add_clinician, make, make_user
from scheduling.views import clock
from scheduling.views.fhir_role_support import element_names, period, stored_role
from scheduling.views.fhir_test_support import NOW, extension, schedule_body, send, token_of

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db
DAY = timedelta(days=1)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _put(profile: ClinicianProfile, body: object, **headers: str) -> "_MonkeyPatchedWSGIResponse":
    return send(
        "put", f"/fhir/PractitionerRole/{profile.pk}", body, token_of(profile.user), **headers
    )


def _own_role() -> tuple[ClinicianProfile, dict[str, object]]:
    profile = add_clinician(make("Department"))
    profile.refresh_from_db()
    return profile, stored_role(token_of(profile.user), profile)


def returns_200_and_records_time_off_when_the_clinician_puts_a_new_period() -> None:
    profile, body = _own_role()
    body["notAvailable"] = [period(STARTS_AT, STARTS_AT + DAY, "Congress")]

    response = _put(profile, body)

    row = TimeOff.objects.get(clinician=profile)
    assert response.status_code == 200
    assert (row.starts_at, row.ends_at, row.reason) == (STARTS_AT, STARTS_AT + DAY, "Congress")
    listed = response.json()["notAvailable"]
    assert [(entry["id"], entry["description"]) for entry in listed] == [(str(row.pk), "Congress")]
    assert AuditLogEntry.objects.filter(action="time_off.create").count() == 1


def returns_200_and_deletes_time_off_when_the_clinician_puts_without_a_stored_period() -> None:
    profile, _ = _own_role()
    row = make("TimeOff", clinician=profile)
    body = stored_role(token_of(profile.user), profile)
    body["notAvailable"] = []

    response = _put(profile, body)

    assert response.status_code == 200
    assert not TimeOff.objects.filter(pk=row.pk).exists()
    assert AuditLogEntry.objects.filter(action="time_off.delete").count() == 1


def returns_400_naming_not_available_entry_when_a_stored_period_is_changed_in_place() -> None:
    profile, _ = _own_role()
    row = make("TimeOff", clinician=profile)
    body = stored_role(token_of(profile.user), profile)
    body["notAvailable"] = [{"id": str(row.pk), **period(STARTS_AT, STARTS_AT + 2 * DAY)}]

    response = _put(profile, body)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.notAvailable[0]"]
    assert TimeOff.objects.get(pk=row.pk).ends_at == STARTS_AT + timedelta(minutes=30)


def returns_400_naming_not_available_when_an_unknown_time_off_id_is_sent() -> None:
    profile, body = _own_role()
    body["notAvailable"] = [
        {"id": "00000000-0000-4000-8000-000000000000", **period(STARTS_AT, STARTS_AT + DAY)}
    ]

    response = _put(profile, body)

    assert response.status_code == 400
    assert element_names(response.json())[0].startswith("PractitionerRole.notAvailable")


@pytest.mark.parametrize(
    ("element", "value", "expected"),
    [
        ("extension", [extension("role-bio", valueString="Other")], "PractitionerRole.extension"),
        (
            "organization",
            {"reference": "Organization/" + "1" * 8 + "-0000-4000-8000-" + "0" * 12},
            "PractitionerRole.organization",
        ),
        ("availableTime", [], "PractitionerRole.availableTime"),
    ],
)
def returns_400_naming_the_element_and_writes_nothing_when_a_clinician_changes_it(
    element: str, value: object, expected: str
) -> None:
    profile, _ = _own_role()
    make("AvailabilityRule", clinician=profile, weekday=3)
    body = stored_role(token_of(profile.user), profile)
    body[element] = value
    body["notAvailable"] = [period(STARTS_AT, STARTS_AT + DAY)]

    response = _put(profile, body)

    assert response.status_code == 400
    assert expected in element_names(response.json())[0]
    assert TimeOff.objects.filter(clinician=profile).count() == 0


def returns_403_when_a_clinician_puts_another_clinicians_role() -> None:
    other = add_clinician(make("Department"))
    body = stored_role(token_of(other.user), other)
    body["notAvailable"] = [period(STARTS_AT, STARTS_AT + DAY)]

    stranger = make_user(role="CLINICIAN")

    response = send("put", f"/fhir/PractitionerRole/{other.pk}", body, token_of(stranger))

    assert response.status_code == 403
    assert TimeOff.objects.count() == 0


def returns_412_when_if_match_is_the_version_before_a_time_off_was_added() -> None:
    profile, body = _own_role()
    before = f'W/"{profile.version}"'
    body["notAvailable"] = [period(STARTS_AT, STARTS_AT + DAY)]
    first = _put(profile, body, **{"If-Match": before})
    again = _put(profile, body, **{"If-Match": before})

    assert (first.status_code, first["ETag"]) == (200, f'W/"{profile.version + 1}"')
    assert again.status_code == 412


def returns_412_when_if_match_is_the_version_before_an_availability_rule_was_added() -> None:
    profile, _ = _own_role()
    clinician = token_of(profile.user)
    before = stored_role(clinician, profile)
    added = send("post", "/fhir/Schedule", schedule_body(profile.user_id, weekday=4), clinician)

    response = _put(profile, before, **{"If-Match": f'W/"{profile.version}"'})

    assert (added.status_code, response.status_code) == (201, 412)
