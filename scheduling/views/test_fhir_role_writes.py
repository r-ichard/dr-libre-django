"""Task 24c: admin writes of PractitionerRole as a FHIR client sends them (bearer token, no cookie,
no Origin). Expected values come from the plan and spec 15.4."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from scheduling.domain.fhir_common import SPECIALTY_SYSTEM
from scheduling.models import AuditLogEntry, ClinicianProfile, Room, Specialty
from scheduling.models.builders import STARTS_AT, add_clinician, make, make_user
from scheduling.views import clock
from scheduling.views.fhir_role_support import (
    element_names,
    new_profile_inputs,
    new_role_body,
    period,
    stored_role,
)
from scheduling.views.fhir_test_support import NOW, extension, send, token_of

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _audit_actions() -> list[str]:
    written = AuditLogEntry.objects.exclude(action="api_client.issue")
    return [entry.action for entry in written.order_by("created_at")]


def _plain_profile() -> ClinicianProfile:
    """No availability rule: a rule bumps the profile to version 2 and blocks a move or a delete."""
    profile = make("ClinicianProfile", department=make("Department"))
    assert isinstance(profile, ClinicianProfile)
    return profile


def _post(body: object, token: str | None) -> "_MonkeyPatchedWSGIResponse":
    return send("post", "/fhir/PractitionerRole", body, token)


def returns_201_with_location_and_etag_when_admin_posts_a_role() -> None:
    user, department, specialty = new_profile_inputs()
    room = make("Room", department=department)
    assert isinstance(room, Room)

    response = _post(new_role_body(user, department, specialty, room), token_of(role="ADMIN"))

    profile = ClinicianProfile.objects.get(user=user)
    assert response.status_code == 201
    assert response["Location"].endswith(f"/fhir/PractitionerRole/{profile.pk}")
    assert response["ETag"] == 'W/"1"'
    assert (profile.department_id, profile.specialty_id, profile.default_room_id) == (
        department.pk,
        specialty.pk,
        room.pk,
    )
    assert (profile.bio, profile.round_robin_weight) == ("Heart rhythm.", 3)
    assert _audit_actions() == ["clinician.create"]


def returns_400_naming_location_when_the_room_belongs_to_another_department() -> None:
    user, department, specialty = new_profile_inputs()
    foreign_room = make("Room")
    assert isinstance(foreign_room, Room)
    body = new_role_body(user, department, specialty, foreign_room)

    response = _post(body, token_of(role="ADMIN"))

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.location"]
    assert ClinicianProfile.objects.filter(user=user).count() == 0


def returns_400_naming_specialty_when_the_specialty_is_inactive() -> None:
    user, department, _ = new_profile_inputs()
    inactive = make("Specialty", is_active=False)
    assert isinstance(inactive, Specialty)
    body = new_role_body(user, department, inactive)

    response = _post(body, token_of(role="ADMIN"))

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.specialty"]


def returns_400_naming_practitioner_when_the_user_has_a_profile() -> None:
    existing = add_clinician(make("Department"))
    _, department, specialty = new_profile_inputs()

    response = _post(new_role_body(existing.user, department, specialty), token_of(role="ADMIN"))

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.practitioner"]


def returns_200_with_new_etag_when_admin_puts_a_changed_bio_with_current_if_match() -> None:
    admin = token_of(role="ADMIN")
    profile = _plain_profile()
    body = stored_role(admin, profile)
    body["extension"] = [
        extension("role-bio", valueString="New bio."),
        extension("role-round-robin-weight", valueInteger=profile.round_robin_weight),
    ]

    response = send(
        "put", f"/fhir/PractitionerRole/{profile.pk}", body, admin, **{"If-Match": 'W/"1"'}
    )

    profile.refresh_from_db()
    assert (response.status_code, response["ETag"], profile.bio) == (200, 'W/"2"', "New bio.")
    metadata = AuditLogEntry.objects.get(action="clinician.update").metadata
    assert metadata["changed_fields"] == ["bio"]


def returns_200_and_keeps_version_when_put_changes_nothing() -> None:
    admin = token_of(role="ADMIN")
    profile = _plain_profile()
    body = stored_role(admin, profile)

    response = send("put", f"/fhir/PractitionerRole/{profile.pk}", body, admin)

    assert (response.status_code, response["ETag"]) == (200, 'W/"1"')
    assert _audit_actions() == []


def returns_400_naming_organization_when_moving_a_clinician_with_upcoming_appointments() -> None:
    admin = token_of(role="ADMIN")
    profile = _plain_profile()
    make(
        "Appointment",
        clinician=profile,
        starts_at=STARTS_AT + timedelta(days=1),
        ends_at=STARTS_AT + timedelta(days=1, minutes=30),
    )
    body = stored_role(admin, profile)
    target = make("Department")
    body["organization"] = {"reference": f"Organization/{target.pk}"}

    response = send("put", f"/fhir/PractitionerRole/{profile.pk}", body, admin)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.organization"]


@pytest.mark.parametrize("method", ["put", "delete"])
def returns_412_when_an_admin_write_carries_a_stale_if_match(method: str) -> None:
    admin = token_of(role="ADMIN")
    profile = add_clinician(make("Department"))
    body = stored_role(admin, profile)

    response = send(
        method, f"/fhir/PractitionerRole/{profile.pk}", body, admin, **{"If-Match": 'W/"9"'}
    )

    assert response.status_code == 412


def returns_409_has_dependents_when_deleting_a_role_with_appointments() -> None:
    profile = add_clinician(make("Department"))
    make("Appointment", clinician=profile)

    response = send("delete", f"/fhir/PractitionerRole/{profile.pk}", {}, token_of(role="ADMIN"))

    assert response.status_code == 409
    assert ClinicianProfile.objects.filter(pk=profile.pk).exists()


def returns_200_outcome_when_deleting_an_unused_role() -> None:
    profile = _plain_profile()

    response = send("delete", f"/fhir/PractitionerRole/{profile.pk}", {}, token_of(role="ADMIN"))

    assert response.status_code == 200
    assert not ClinicianProfile.objects.filter(pk=profile.pk).exists()
    assert _audit_actions() == ["clinician.delete"]


def returns_400_naming_available_time_when_an_admin_body_changes_it() -> None:
    admin = token_of(role="ADMIN")
    profile = add_clinician(make("Department"))
    body = stored_role(admin, profile)
    body["availableTime"] = [
        {"daysOfWeek": ["sat"], "availableStartTime": "01:00:00", "availableEndTime": "02:00:00"}
    ]

    response = send("put", f"/fhir/PractitionerRole/{profile.pk}", body, admin)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.availableTime"]


def returns_400_naming_not_available_when_an_admin_changes_it() -> None:
    admin = token_of(role="ADMIN")
    profile = add_clinician(make("Department"))
    body = stored_role(admin, profile)
    body["notAvailable"] = [period(STARTS_AT, STARTS_AT + timedelta(days=1))]

    response = send("put", f"/fhir/PractitionerRole/{profile.pk}", body, admin)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.notAvailable"]


def returns_200_when_an_admin_puts_back_the_stored_not_available() -> None:
    admin = token_of(role="ADMIN")
    profile = add_clinician(make("Department"))
    make("TimeOff", clinician=profile, reason="Congress")
    body = stored_role(admin, profile)

    response = send("put", f"/fhir/PractitionerRole/{profile.pk}", body, admin)

    assert response.status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def returns_401_when_no_token_writes_a_role(method: str) -> None:
    profile = add_clinician(make("Department"))
    path = "/fhir/PractitionerRole" if method == "post" else f"/fhir/PractitionerRole/{profile.pk}"

    response = send(method, path, {}, None)

    assert response.status_code == 401


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def returns_403_when_a_patient_writes_a_role(method: str) -> None:
    profile = add_clinician(make("Department"))
    path = "/fhir/PractitionerRole" if method == "post" else f"/fhir/PractitionerRole/{profile.pk}"

    response = send(method, path, {}, token_of(make_user(role="PATIENT")))

    assert response.status_code == 403


@pytest.mark.parametrize("method", ["post", "delete"])
def returns_403_when_a_clinician_posts_or_deletes_a_role(method: str) -> None:
    profile = add_clinician(make("Department"))
    path = "/fhir/PractitionerRole" if method == "post" else f"/fhir/PractitionerRole/{profile.pk}"

    response = send(method, path, {}, token_of(profile.user))

    assert response.status_code == 403
    assert ClinicianProfile.objects.filter(pk=profile.pk).exists()


def returns_400_naming_available_time_when_admin_posts_a_role_with_it() -> None:
    user, department, specialty = new_profile_inputs()
    body = new_role_body(user, department, specialty)
    body["availableTime"] = [
        {"daysOfWeek": ["sat"], "availableStartTime": "01:00:00", "availableEndTime": "02:00:00"}
    ]

    response = _post(body, token_of(role="ADMIN"))

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.availableTime"]
    assert not ClinicianProfile.objects.filter(user=user).exists()


def returns_400_naming_specialty_when_the_specialty_code_is_unknown() -> None:
    user, department, specialty = new_profile_inputs()
    body = new_role_body(user, department, specialty)
    body["specialty"] = [{"coding": [{"system": SPECIALTY_SYSTEM, "code": "no-such-code"}]}]

    response = _post(body, token_of(role="ADMIN"))

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.specialty"]
    assert not ClinicianProfile.objects.filter(user=user).exists()
