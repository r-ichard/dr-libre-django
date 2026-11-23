"""Sections 15.2, 15.4: Schedule writes by the owning clinician only, via the use cases of
task 17, and PractitionerRole.availableTime and the application slots following every write."""

import pytest

from scheduling.models import AvailabilityRule
from scheduling.models.builders import add_clinician, make_clinic
from scheduling.views import clock
from scheduling.views.fhir_test_support import (
    FHIR_JSON,
    NOW,
    client_for,
    get,
    schedule_body,
    send,
    token_of,
)

pytestmark = pytest.mark.django_db

TUESDAY_SLOTS = "from=2030-01-08T00:00:00Z&to=2030-01-09T00:00:00Z"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def returns_201_with_location_and_etag_when_clinician_creates_schedule() -> None:
    clinic = make_clinic()
    body = schedule_body(clinic.clinician.user_id)

    response = send("post", "/fhir/Schedule", body, token_of(clinic.clinician.user))

    assert response.status_code == 201
    created = AvailabilityRule.objects.get(weekday=2, clinician=clinic.clinician)
    assert response["Location"].endswith(f"/fhir/Schedule/{created.pk}")
    assert response["ETag"] == f'W/"{created.version}"'
    assert response.json()["id"] == str(created.pk)
    assert response["Content-Type"].startswith(FHIR_JSON)


@pytest.mark.parametrize("who", ["admin", "other_clinician"])
def returns_403_and_stores_nothing_when_not_the_owner_creates_schedule(who: str) -> None:
    clinic = make_clinic()
    other = add_clinician(clinic.department)
    token = token_of(role="ADMIN") if who == "admin" else token_of(other.user)
    body = schedule_body(clinic.clinician.user_id)

    response = send("post", "/fhir/Schedule", body, token)

    assert response.status_code == 403
    assert response.json()["resourceType"] == "OperationOutcome"
    assert not AvailabilityRule.objects.filter(weekday=2).exists()


def returns_401_when_schedule_created_without_token() -> None:
    clinic = make_clinic()

    response = send("post", "/fhir/Schedule", schedule_body(clinic.clinician.user_id), None)

    assert response.status_code == 401


def returns_422_naming_rule_violation_when_new_schedule_overlaps_another() -> None:
    clinic = make_clinic()
    body = schedule_body(clinic.clinician.user_id, weekday=1, start="10:00:00", end="11:00:00")

    response = send("post", "/fhir/Schedule", body, token_of(clinic.clinician.user))

    assert response.status_code == 422
    issue = response.json()["issue"][0]
    assert issue["code"] == "business-rule"


def returns_400_naming_element_when_schedule_body_has_unknown_element() -> None:
    clinic = make_clinic()
    body = {**schedule_body(clinic.clinician.user_id), "comment": "hello"}

    response = send("post", "/fhir/Schedule", body, token_of(clinic.clinician.user))

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Schedule.comment"]


def returns_400_naming_id_when_create_body_carries_an_id() -> None:
    clinic = make_clinic()
    body = {**schedule_body(clinic.clinician.user_id), "id": "abc"}

    response = send("post", "/fhir/Schedule", body, token_of(clinic.clinician.user))

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Schedule.id"]


def returns_200_and_new_version_when_owner_updates_schedule() -> None:
    clinic = make_clinic()
    rule = AvailabilityRule.objects.get(clinician=clinic.clinician)
    body = {**schedule_body(clinic.clinician.user_id, weekday=1, start="09:00:00", end="12:00:00")}
    body["id"] = str(rule.pk)
    body["planningHorizon"] = {"start": "2030-01-01"}

    response = send("put", f"/fhir/Schedule/{rule.pk}", body, token_of(clinic.clinician.user))

    rule.refresh_from_db()
    assert response.status_code == 200
    assert response["ETag"] == f'W/"{rule.version}"'
    assert rule.end_time.hour == 12


def returns_400_naming_id_when_put_body_has_another_resource_id() -> None:
    clinic = make_clinic()
    rule = AvailabilityRule.objects.get(clinician=clinic.clinician)
    body = {**schedule_body(clinic.clinician.user_id), "id": "someone-else"}

    response = send("put", f"/fhir/Schedule/{rule.pk}", body, token_of(clinic.clinician.user))

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Schedule.id"]


def returns_412_when_update_if_match_is_stale() -> None:
    clinic = make_clinic()
    rule = AvailabilityRule.objects.get(clinician=clinic.clinician)
    body = {**schedule_body(clinic.clinician.user_id, weekday=1), "id": str(rule.pk)}
    body["planningHorizon"] = {"start": "2030-01-01"}

    response = send(
        "put",
        f"/fhir/Schedule/{rule.pk}",
        body,
        token_of(clinic.clinician.user),
        **{"If-Match": f'W/"{rule.version + 5}"'},
    )

    assert response.status_code == 412
    assert response.json()["resourceType"] == "OperationOutcome"


def returns_403_when_other_clinician_deletes_schedule() -> None:
    clinic = make_clinic()
    rule = AvailabilityRule.objects.get(clinician=clinic.clinician)
    other = add_clinician(clinic.department)

    response = client_for(token_of(other.user)).delete(f"/fhir/Schedule/{rule.pk}")

    assert response.status_code in (403, 404)
    assert AvailabilityRule.objects.filter(pk=rule.pk).exists()


def returns_schedule_gone_from_search_role_and_slots_after_owner_deletes_it() -> None:
    clinic = make_clinic()
    token = token_of(clinic.clinician.user)
    created = send("post", "/fhir/Schedule", schedule_body(clinic.clinician.user_id), token)
    schedule_id = created.json()["id"]
    role = f"/fhir/PractitionerRole/{clinic.clinician.pk}"
    slots = f"/api/v1/slots?appointment_type_id={clinic.appointment_type.pk}&{TUESDAY_SLOTS}"

    after_create = (
        [item["resource"]["id"] for item in get("/fhir/Schedule", token).json()["entry"]],
        _available_days(get(role, token).json()),
        len(client_for(None).get(slots).json()["slots"]),
    )
    deleted = client_for(token).delete(f"/fhir/Schedule/{schedule_id}")
    after_delete = (
        [item["resource"]["id"] for item in get("/fhir/Schedule", token).json()["entry"]],
        _available_days(get(role, token).json()),
        len(client_for(None).get(slots).json()["slots"]),
    )

    assert deleted.status_code == 200
    assert schedule_id in after_create[0] and 2 in after_create[1] and after_create[2] == 2
    assert schedule_id not in after_delete[0] and 2 not in after_delete[1]
    assert after_delete[2] == 0


def _available_days(role: dict[str, object]) -> set[int]:
    days: set[int] = set()
    for block in role.get("availableTime", []):  # type: ignore[attr-defined]
        days.update(_weekday_number(name) for name in block["daysOfWeek"])
    return days


def _weekday_number(code: str) -> int:
    return ["sun", "mon", "tue", "wed", "thu", "fri", "sat"].index(code)
