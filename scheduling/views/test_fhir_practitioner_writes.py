"""Section 15.4: admins write Practitioner as clients send them (bearer token, no cookie,
no Origin). Expected values come from the plan, ADR 0009 and spec 15.4."""

from typing import TYPE_CHECKING

import pytest

from scheduling.models import AuditLogEntry, ClinicianProfile, Session, SignInLink, User
from scheduling.models.builders import add_clinician, make, make_user
from scheduling.views import clock
from scheduling.views.fhir_role_support import element_names
from scheduling.views.fhir_test_support import NOW, get, send, token_of

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _practitioner() -> ClinicianProfile:
    """No availability rule: a rule adds nothing here, the user and profile are the subject."""
    profile = make("ClinicianProfile", department=make("Department"))
    assert isinstance(profile, ClinicianProfile)
    return profile


def _stored(token: str, profile: ClinicianProfile) -> dict[str, object]:
    body = get(f"/fhir/Practitioner/{profile.user_id}", token).json()
    assert isinstance(body, dict)  # noqa: S101
    return body


def _put(
    profile: ClinicianProfile, body: object, token: str | None, **headers: str
) -> "_MonkeyPatchedWSGIResponse":
    return send("put", f"/fhir/Practitioner/{profile.user_id}", body, token, **headers)


def _audit_actions() -> list[str]:
    written = AuditLogEntry.objects.exclude(action="api_client.issue")
    return [entry.action for entry in written.order_by("created_at")]


def _version_of(body: dict[str, object]) -> int:
    """A profile insert already moved the user's version (ADR 0003), so a test reads it."""
    meta = body["meta"]
    assert isinstance(meta, dict)  # noqa: S101
    return int(meta["versionId"])


def _with(body: dict[str, object], **changes: object) -> dict[str, object]:
    return {**body, **changes}


def returns_200_with_new_etag_when_admin_puts_a_changed_name() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    stored = _stored(admin, profile)
    version = _version_of(stored)
    body = _with(stored, name=[{"text": "Ada Lovelace"}])

    response = _put(profile, body, admin, **{"If-Match": f'W/"{version}"'})

    profile.user.refresh_from_db()
    assert response.status_code == 200
    assert response["ETag"] == f'W/"{version + 1}"'
    assert profile.user.full_name == "Ada Lovelace"
    metadata = AuditLogEntry.objects.get(action="user.update").metadata
    assert metadata["changed_fields"] == ["full_name"]


def returns_200_and_keeps_version_when_put_changes_nothing() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()

    stored = _stored(admin, profile)

    response = _put(profile, stored, admin)

    assert response.status_code == 200
    assert response["ETag"] == f'W/"{_version_of(stored)}"'
    assert _audit_actions() == []


def returns_200_with_unverified_email_and_no_sessions_or_links_when_email_changes() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    profile.user.refresh_from_db()
    profile.user.email_verified_at = NOW
    profile.user.save()
    make("Session", user=profile.user)
    make("SignInLink", patient=profile.user)
    body = _with(
        _stored(admin, profile), telecom=[{"system": "email", "value": "new.address@example.com"}]
    )

    response = _put(profile, body, admin)

    profile.user.refresh_from_db()
    assert response.status_code == 200
    assert profile.user.email == "new.address@example.com"
    assert profile.user.email_verified_at is None
    assert Session.objects.filter(user=profile.user).count() == 0
    links = SignInLink.objects.filter(patient=profile.user)
    assert links.filter(cancelled_at__isnull=True).count() == 0


def returns_200_and_ends_sessions_but_revokes_no_token_when_admin_puts_active_false() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    token_of(profile.user)
    make("Session", user=profile.user)

    response = _put(profile, _with(_stored(admin, profile), active=False), admin)

    profile.user.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["active"] is False
    assert profile.user.is_active is False
    assert Session.objects.filter(user=profile.user).count() == 0
    assert profile.user.apiclient_set.filter(revoked_at__isnull=False).count() == 0
    assert _audit_actions() == ["user.deactivate"]


def returns_401_for_the_deactivated_users_token_and_200_again_when_reactivated() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    own_token = token_of(profile.user)
    stored = _stored(admin, profile)
    _put(profile, _with(stored, active=False), admin)

    while_inactive = get("/fhir/Practitioner", own_token)
    _put(profile, _with(_stored(admin, profile), active=True), admin)
    after_reactivation = get("/fhir/Practitioner", own_token)

    assert (while_inactive.status_code, after_reactivation.status_code) == (401, 200)
    assert "user.activate" in _audit_actions()


def returns_200_and_moves_version_when_put_changes_the_qualification() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    body = _with(_stored(admin, profile), qualification=[{"code": {"text": "Prof"}}])

    response = _put(profile, body, admin)

    profile.refresh_from_db()
    assert (response.status_code, profile.title) == (200, "Prof")
    assert response["ETag"] != 'W/"1"'


def returns_412_for_the_old_if_match_after_the_profile_title_changes() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    body = _stored(admin, profile)
    profile.title = "Prof"
    profile.save()

    response = _put(profile, _with(body, active=True), admin, **{"If-Match": 'W/"1"'})

    assert response.status_code == 412


def returns_412_when_if_match_is_stale_on_put_and_delete() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    body = _stored(admin, profile)

    put = _put(profile, body, admin, **{"If-Match": 'W/"9"'})
    delete = send(
        "delete", f"/fhir/Practitioner/{profile.user_id}", {}, admin, **{"If-Match": 'W/"9"'}
    )

    assert (put.status_code, delete.status_code) == (412, 412)


def returns_400_naming_telecom_when_the_phone_differs() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    telecom = [
        {"system": "email", "value": profile.user.email},
        {"system": "phone", "value": "+31 20 555 0100"},
    ]

    response = _put(profile, _with(_stored(admin, profile), telecom=telecom), admin)

    assert response.status_code == 400
    assert element_names(response.json()) == ["Practitioner.telecom"]
    assert User.objects.get(pk=profile.user_id).phone == ""


def returns_400_naming_name_when_the_name_is_empty() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()

    response = _put(profile, _with(_stored(admin, profile), name=[{"text": ""}]), admin)

    assert response.status_code == 400
    assert element_names(response.json()) == ["Practitioner.name"]


def returns_400_naming_telecom_when_the_email_is_taken() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    taken = make_user(email="taken@example.com")
    body = _with(_stored(admin, profile), telecom=[{"system": "email", "value": taken.email}])

    response = _put(profile, body, admin)

    assert response.status_code == 400
    assert element_names(response.json()) == ["Practitioner.telecom"]


def returns_400_naming_active_when_an_admin_with_a_profile_deactivates_its_own_user() -> None:
    admin_user = make_user(role="ADMIN")
    make("ClinicianProfile", user=admin_user)
    make_user(role="ADMIN")
    admin = token_of(admin_user)
    profile = ClinicianProfile.objects.get(user=admin_user)

    response = _put(profile, _with(_stored(admin, profile), active=False), admin)

    assert response.status_code == 400
    assert element_names(response.json()) == ["Practitioner.active"]
    assert User.objects.get(pk=admin_user.pk).is_active is True


def returns_404_when_put_or_delete_names_a_user_without_a_profile_or_unknown() -> None:
    admin = token_of(role="ADMIN")
    bare = make_user(role="CLINICIAN")
    unknown = "00000000-0000-4000-8000-000000000001"

    answers = [
        send(method, f"/fhir/Practitioner/{identifier}", {"resourceType": "Practitioner"}, admin)
        for method in ("put", "delete")
        for identifier in (bare.pk, unknown)
    ]

    assert [answer.status_code for answer in answers] == [404, 404, 404, 404]


def returns_409_has_dependents_naming_the_profile_when_deleting_a_practitioner() -> None:
    profile = _practitioner()

    response = send("delete", f"/fhir/Practitioner/{profile.user_id}", {}, token_of(role="ADMIN"))

    issue = response.json()["issue"][0]
    assert response.status_code == 409
    assert issue["extension"][0]["valueCode"] == "has_dependents"
    assert "1 clinician profile" in issue["diagnostics"]
    assert User.objects.filter(pk=profile.user_id).exists()
    assert _audit_actions() == []


def returns_409_with_appointment_count_when_the_practitioner_has_appointments() -> None:
    profile = add_clinician(make("Department"))
    make("Appointment", clinician=profile)

    response = send("delete", f"/fhir/Practitioner/{profile.user_id}", {}, token_of(role="ADMIN"))

    assert response.status_code == 409
    assert "1 appointment" in response.json()["issue"][0]["diagnostics"]
    assert User.objects.filter(pk=profile.user_id).exists()


def returns_405_with_allow_put_delete_get_when_posting_a_practitioner() -> None:
    body = {"resourceType": "Practitioner", "name": [{"text": "New Person"}]}

    response = send("post", "/fhir/Practitioner", body, token_of(role="ADMIN"))

    assert response.status_code == 405
    allowed = {part.strip() for part in response["Allow"].split(",")}
    assert {"GET", "PUT", "DELETE"} <= allowed
    assert "POST" not in allowed


@pytest.mark.parametrize("method", ["put", "delete"])
@pytest.mark.parametrize("role", ["CLINICIAN", "PATIENT"])
def returns_403_before_the_body_for_a_clinician_or_patient_token(method: str, role: str) -> None:
    profile = _practitioner()

    response = send(
        method, f"/fhir/Practitioner/{profile.user_id}", "{garbage", token_of(role=role)
    )

    assert response.status_code == 403
    assert User.objects.get(pk=profile.user_id).full_name == profile.user.full_name


@pytest.mark.parametrize("method", ["put", "delete"])
def returns_401_before_the_body_without_a_token(method: str) -> None:
    profile = _practitioner()

    response = send(method, f"/fhir/Practitioner/{profile.user_id}", "{garbage", None)

    assert response.status_code == 401


def returns_403_when_the_clinician_puts_its_own_practitioner() -> None:
    profile = _practitioner()
    own = token_of(profile.user)

    response = _put(profile, {"resourceType": "Practitioner"}, own)

    assert response.status_code == 403


def returns_update_and_delete_but_not_create_in_the_capability_statement() -> None:
    statement = get("/fhir/metadata").json()
    resources = {item["type"]: item for item in statement["rest"][0]["resource"]}

    codes = [item["code"] for item in resources["Practitioner"]["interaction"]]

    assert sorted(codes) == ["delete", "read", "search-type", "update"]


def returns_200_and_stays_inactive_when_put_omits_active_for_a_deactivated_user() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    _put(profile, _with(_stored(admin, profile), active=False), admin)
    omitted = {key: value for key, value in _stored(admin, profile).items() if key != "active"}

    response = _put(profile, omitted, admin)

    assert response.status_code == 200
    assert User.objects.get(pk=profile.user_id).is_active is False


def returns_400_naming_telecom_when_an_element_has_an_unknown_system() -> None:
    admin = token_of(role="ADMIN")
    profile = _practitioner()
    telecom = [
        {"system": "email", "value": profile.user.email},
        {"system": "fax", "value": "+31 20 555 0101"},
    ]

    response = _put(profile, _with(_stored(admin, profile), telecom=telecom), admin)

    assert response.status_code == 400
    assert element_names(response.json()) == ["Practitioner.telecom"]
