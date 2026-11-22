"""Task 24b2: an admin writes the specialty list as one CodeSystem, as a FHIR client sends it
(bearer token, no cookie, no Origin). Expected values come from the plan and spec 15.4."""

import pytest

from scheduling.models import AuditLogEntry, Specialty
from scheduling.models.builders import add_clinician, make
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client
from scheduling.views.fhir_specialty_support import (
    LIST_PATH,
    concept,
    concept_codes,
    concepts_of,
    current_list,
    specialty_audit,
    stored,
    with_concepts,
)
from scheduling.views.fhir_test_support import NOW, get, send, token_of

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _etag(token: str) -> str:
    return get(LIST_PATH, token)["ETag"]


def _version(token: str) -> int:
    return int(_etag(token).removeprefix('W/"').removesuffix('"'))


def _publish(specialty: Specialty) -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    add_clinician(department, specialty=specialty)


def _public_names() -> list[str]:
    results = browser_api_client().get("/api/v1/search/specialties").json()["results"]
    return [result["name"] for result in results]


def returns_200_with_the_version_raised_when_admin_adds_a_concept() -> None:
    admin = token_of(role="ADMIN")
    before = _version(admin)
    body = with_concepts(admin, concept("neuro", "Neurology"))

    response = send("put", LIST_PATH, body, admin)

    row = Specialty.objects.get(code="neuro")
    assert (response.status_code, row.name, row.is_active) == (200, "Neurology", True)
    assert (_version(admin), specialty_audit()) == (before + 1, [("specialty.create", str(row.pk))])
    assert concept_codes(_public_token()) == ["neuro"]


def _public_token() -> str:
    return token_of(role="PATIENT")


def returns_200_when_admin_renames_a_concept_matching_its_code_ignoring_case() -> None:
    admin = token_of(role="ADMIN")
    row = stored("cardio", "Cardiology")
    body = with_concepts(admin, concept("CARDIO", "Heart care"))

    response = send("put", LIST_PATH, body, admin)

    row.refresh_from_db()
    entry = AuditLogEntry.objects.get(action="specialty.update")
    assert (response.status_code, row.name, row.code) == (200, "Heart care", "cardio")
    assert entry.metadata["changed_fields"] == ["name"]
    assert Specialty.objects.count() == 1


def returns_200_and_hides_it_from_public_reads_when_admin_marks_a_concept_inactive() -> None:
    admin = token_of(role="ADMIN")
    row = stored("cardio", "Cardiology")
    _publish(row)
    offered = _public_names()

    send("put", LIST_PATH, with_concepts(admin, concept("cardio", "Cardiology", True)), admin)

    row.refresh_from_db()
    listed = concepts_of(admin)
    assert (offered, row.is_active, _public_names()) == (["Cardiology"], False, [])
    assert listed == [concept("cardio", "Cardiology", True)]
    assert concept_codes(_public_token()) == []


def returns_200_and_offers_it_again_when_admin_drops_the_inactive_property() -> None:
    admin = token_of(role="ADMIN")
    row = stored("cardio", "Cardiology", is_active=False)
    _publish(row)

    response = send("put", LIST_PATH, with_concepts(admin, concept("cardio", "Cardiology")), admin)

    row.refresh_from_db()
    assert (response.status_code, row.is_active, _public_names()) == (200, True, ["Cardiology"])


def returns_200_with_inactive_concepts_for_an_admin_read_and_without_for_the_public() -> None:
    admin = token_of(role="ADMIN")
    stored("cardio", "Cardiology", is_active=False)
    stored("derma", "Dermatology")

    shown = current_list(admin)

    assert (shown["count"], concept_codes(admin)) == (2, ["cardio", "derma"])
    assert concept_codes(_public_token()) == ["derma"]


def returns_200_when_admin_omits_an_unused_concept() -> None:
    admin = token_of(role="ADMIN")
    kept = stored("cardio", "Cardiology")
    gone = stored("derma", "Dermatology")

    response = send("put", LIST_PATH, with_concepts(admin, concept("cardio", "Cardiology")), admin)

    assert response.status_code == 200
    assert list(Specialty.objects.values_list("pk", flat=True)) == [kept.pk]
    assert specialty_audit() == [("specialty.delete", str(gone.pk))]


def returns_409_has_dependents_with_counts_and_applies_nothing_when_a_used_concept_is_omitted() -> (
    None
):
    admin = token_of(role="ADMIN")
    used = stored("cardio", "Cardiology")
    stored("derma", "Dermatology")
    add_clinician(make("Department"), specialty=used)
    body = with_concepts(admin, concept("derma", "Skin care"), concept("neuro", "Neurology"))

    response = send("put", LIST_PATH, body, admin)

    issue = response.json()["issue"][0]
    assert response.status_code == 409
    assert issue["extension"][0]["valueCode"] == "has_dependents"
    assert "1 clinician" in issue["diagnostics"]
    assert sorted(Specialty.objects.values_list("name", flat=True)) == [
        "Cardiology",
        "Dermatology",
    ]
    assert specialty_audit() == []


def returns_200_and_applies_both_when_one_body_adds_one_and_renames_another() -> None:
    admin = token_of(role="ADMIN")
    old = stored("cardio", "Cardiology")
    body = with_concepts(admin, concept("cardio", "Heart care"), concept("neuro", "Neurology"))

    response = send("put", LIST_PATH, body, admin)

    created = Specialty.objects.get(code="neuro")
    assert response.status_code == 200
    assert sorted(specialty_audit()) == sorted(
        [("specialty.update", str(old.pk)), ("specialty.create", str(created.pk))]
    )


def returns_400_and_applies_neither_when_the_second_change_is_refused() -> None:
    admin = token_of(role="ADMIN")
    stored("cardio", "Cardiology")
    body = with_concepts(admin, concept("cardio", "Heart care"), concept("neuro", "   "))

    response = send("put", LIST_PATH, body, admin)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["CodeSystem.concept[1].display"]
    assert list(Specialty.objects.values_list("name", flat=True)) == ["Cardiology"]
    assert specialty_audit() == []


def returns_200_and_keeps_the_version_when_the_body_changes_nothing() -> None:
    admin = token_of(role="ADMIN")
    stored("cardio", "Cardiology", is_active=False)
    before = _etag(admin)

    response = send("put", LIST_PATH, current_list(admin), admin)

    assert (response.status_code, response["ETag"], _etag(admin)) == (200, before, before)
    assert specialty_audit() == []


def returns_200_when_if_match_is_current_and_412_when_it_is_stale() -> None:
    admin = token_of(role="ADMIN")
    stored("cardio", "Cardiology")
    current = _etag(admin)
    renamed = with_concepts(admin, concept("cardio", "Heart care"))

    stale = send("put", LIST_PATH, renamed, admin, **{"If-Match": 'W/"999"'})
    applied = send("put", LIST_PATH, renamed, admin, **{"If-Match": current})

    assert (stale.status_code, applied.status_code) == (412, 200)
    assert list(Specialty.objects.values_list("name", flat=True)) == ["Heart care"]
    assert len(specialty_audit()) == 1


@pytest.mark.parametrize("role", ["CLINICIAN", "PATIENT"])
def returns_403_and_writes_nothing_when_a_non_admin_writes(role: str) -> None:
    body = with_concepts(token_of(role="ADMIN"), concept("neuro", "Neurology"))

    response = send("put", LIST_PATH, body, token_of(role=role))

    assert response.status_code == 403
    assert (Specialty.objects.count(), specialty_audit()) == (0, [])


def returns_401_and_writes_nothing_when_no_token_writes() -> None:
    body = with_concepts(token_of(role="ADMIN"), concept("neuro", "Neurology"))

    response = send("put", LIST_PATH, body, None)

    assert response.status_code == 401
    assert Specialty.objects.count() == 0


@pytest.mark.parametrize(
    ("concepts", "expression"),
    [
        ([concept("neuro", "A"), concept("NEURO", "B")], "CodeSystem.concept[1].code"),
        ([concept("neuro", "")], "CodeSystem.concept[0].display"),
        ([concept("bad code!", "Neurology")], "CodeSystem.concept[0].code"),
    ],
)
def returns_400_naming_the_element_when_a_concept_is_invalid(
    concepts: list[dict[str, object]], expression: str
) -> None:
    admin = token_of(role="ADMIN")

    response = send("put", LIST_PATH, with_concepts(admin, *concepts), admin)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == [expression]
    assert Specialty.objects.count() == 0


def returns_400_naming_count_when_the_count_is_not_the_number_of_concepts() -> None:
    admin = token_of(role="ADMIN")
    body = with_concepts(admin, concept("neuro", "Neurology"))
    body["count"] = 7

    response = send("put", LIST_PATH, body, admin)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["CodeSystem.count"]


def returns_404_when_putting_another_code_system_id() -> None:
    admin = token_of(role="ADMIN")

    response = send("put", "/fhir/CodeSystem/other", current_list(admin), admin)

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("put", "/fhir/ValueSet/specialty"),
        ("post", "/fhir/ValueSet"),
        ("delete", "/fhir/ValueSet/specialty"),
        ("post", "/fhir/CodeSystem"),
        ("delete", "/fhir/CodeSystem/specialty"),
    ],
)
def returns_405_with_the_declared_allow_when_an_unsupported_interaction_is_used(
    method: str, path: str
) -> None:
    admin = token_of(role="ADMIN")

    response = send(method, path, current_list(admin), admin)

    assert response.status_code == 405
    allowed = "GET, PUT" if path == "/fhir/CodeSystem/specialty" else "GET"
    assert response["Allow"] == allowed


def returns_the_capability_statement_with_update_for_the_code_system_only() -> None:
    rest = get("/fhir/metadata").json()["rest"][0]["resource"]

    interactions = {
        item["type"]: sorted(entry["code"] for entry in item["interaction"]) for item in rest
    }
    assert interactions["CodeSystem"] == ["read", "search-type", "update"]
    assert interactions["ValueSet"] == ["read", "search-type"]


def returns_409_and_undoes_the_earlier_removal_when_a_later_removal_is_refused() -> None:
    admin = token_of(role="ADMIN")
    stored("aaa", "Free")
    add_clinician(make("Department"), specialty=stored("cardio", "Cardiology"))

    response = send("put", LIST_PATH, with_concepts(admin), admin)

    assert response.status_code == 409
    assert sorted(Specialty.objects.values_list("code", flat=True)) == ["aaa", "cardio"]
    assert specialty_audit() == []


def returns_200_and_changes_nothing_when_the_body_code_differs_only_in_case_from_a_stored_one() -> (
    None
):
    admin = token_of(role="ADMIN")
    row = stored("Cardio", "Cardiology")

    response = send("put", LIST_PATH, with_concepts(admin, concept("cardio", "Cardiology")), admin)

    assert (response.status_code, list(Specialty.objects.values_list("pk", flat=True))) == (
        200,
        [row.pk],
    )
    assert specialty_audit() == []


def returns_the_inactive_concept_in_the_answer_when_admin_deactivates_it() -> None:
    admin = token_of(role="ADMIN")
    stored("cardio", "Cardiology")

    response = send(
        "put", LIST_PATH, with_concepts(admin, concept("cardio", "Cardiology", True)), admin
    )

    assert response.json()["concept"] == [concept("cardio", "Cardiology", True)]


def returns_400_naming_the_url_when_the_body_carries_another_system() -> None:
    admin = token_of(role="ADMIN")
    body = with_concepts(admin, concept("neuro", "Neurology"))
    body["url"] = "https://example.org/other"

    response = send("put", LIST_PATH, body, admin)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["CodeSystem.url"]
    assert Specialty.objects.count() == 0


def returns_400_naming_the_property_when_a_concept_lists_the_inactive_property_twice() -> None:
    admin = token_of(role="ADMIN")
    item = concept("neuro", "Neurology")
    item["property"] = [
        {"code": "inactive", "valueBoolean": True},
        {"code": "inactive", "valueBoolean": False},
    ]

    response = send("put", LIST_PATH, with_concepts(admin, item), admin)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["CodeSystem.concept[0].property"]
    assert Specialty.objects.count() == 0
