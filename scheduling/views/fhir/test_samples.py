"""Section 15.1: every sample /fhir answers is free of empty arrays, objects, strings and
nulls, the rule the HL7 validator enforces in `make fhir-validate`."""

import pytest
from django.utils import timezone

from scheduling.demo_seed.seed_support import run_seed, seed_environment
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_communication import NOTIFICATION_KIND_WORDS
from scheduling.domain.fhir_declaration import FHIR_RESOURCES
from scheduling.domain.request_context import RequestContext
from scheduling.models import Notification, User
from scheduling.use_cases.request_context import bind_request_context
from scheduling.views.fhir.samples import sample_documents

pytestmark = pytest.mark.django_db

__all__ = ["seed_environment"]


def _empty_paths(value: object, path: str = "$") -> list[str]:
    if value is None or (isinstance(value, str | list | dict) and len(value) == 0):
        return [path]
    if isinstance(value, dict):
        return [
            found for key, item in value.items() for found in _empty_paths(item, f"{path}.{key}")
        ]
    if isinstance(value, list):
        return [
            found
            for index, item in enumerate(value)
            for found in _empty_paths(item, f"{path}[{index}]")
        ]
    return []


def returns_no_empty_value_when_every_sample_is_walked(seed_environment: None) -> None:
    run_seed()
    admin = User.objects.filter(role="ADMIN").first()
    assert admin is not None
    with bind_request_context(RequestContext("samples-test", timezone.now())):
        documents: dict[str, Resource] = sample_documents(admin)

    assert len(documents) >= 30
    found = {name: _empty_paths(body) for name, body in documents.items()}
    assert {name: paths for name, paths in found.items() if paths} == {}


def returns_a_sample_of_every_type_in_both_views_when_samples_are_built(
    seed_environment: None,
) -> None:
    run_seed()
    admin = User.objects.filter(role="ADMIN").first()
    assert admin is not None
    with bind_request_context(RequestContext("samples-test", timezone.now())):
        names = set(sample_documents(admin))

    for view in ("public", "staff"):
        for kind in (
            "Organization",
            "Location",
            "HealthcareService",
            "CodeSystem",
            "ValueSet",
            "Practitioner",
            "PractitionerRole",
        ):
            assert f"{kind}-read-{view}" in names
        assert {
            f"PractitionerRole-include-{view}",
            f"metadata-{view}",
            f"OperationOutcome-{view}",
        } <= names


def returns_a_staff_sample_for_every_declared_type_when_samples_are_built(
    seed_environment: None,
) -> None:
    run_seed()
    admin = User.objects.filter(role="ADMIN").first()
    assert admin is not None
    with bind_request_context(RequestContext("samples-test", timezone.now())):
        names = set(sample_documents(admin))

    missing = [
        declaration.type
        for declaration in FHIR_RESOURCES
        if not any(
            name.startswith(f"{declaration.type}-") and name.endswith("-staff") for name in names
        )
    ]
    assert missing == []


INTERACTION_SUFFIX = {
    "read": "read",
    "search-type": "search",
    "create": "create",
    "update": "update",
    "delete": "delete",
}


def returns_a_staff_sample_for_every_interaction_and_include_of_every_type(
    seed_environment: None,
) -> None:
    run_seed()
    admin = User.objects.filter(role="ADMIN").first()
    assert admin is not None
    with bind_request_context(RequestContext("samples-test", timezone.now())):
        names = set(sample_documents(admin))

    expected = {
        f"{declaration.type}-{INTERACTION_SUFFIX[interaction]}-staff"
        for declaration in FHIR_RESOURCES
        for interaction in declaration.interactions
    } | {
        f"{declaration.type}-include-staff"
        for declaration in FHIR_RESOURCES
        if declaration.includes
    }
    assert sorted(expected - names) == []


def returns_a_refusal_sample_for_each_type_the_task_names_when_samples_are_built(
    seed_environment: None,
) -> None:
    run_seed()
    admin = User.objects.filter(role="ADMIN").first()
    assert admin is not None
    with bind_request_context(RequestContext("samples-test", timezone.now())):
        names = set(sample_documents(admin))

    refusals = {f"{kind}-refusal-staff" for kind in ("Appointment", "AppointmentResponse")}
    refusals |= {f"{kind}-refusal-staff" for kind in ("Communication", "AuditEvent")}
    assert sorted(refusals - names) == []


def _staff_samples() -> dict[str, Resource]:
    run_seed()
    admin = User.objects.filter(role="ADMIN").first()
    assert admin is not None
    with bind_request_context(RequestContext("samples-test", timezone.now())):
        return sample_documents(admin)


def _entry_types(bundle: Resource) -> set[str]:
    entries: list[dict[str, dict[str, str]]] = bundle["entry"]  # type: ignore[assignment]
    return {entry["resource"]["resourceType"] for entry in entries}


def returns_every_included_type_when_the_appointment_include_sample_is_read(
    seed_environment: None,
) -> None:
    samples = _staff_samples()

    assert _entry_types(samples["Appointment-include-staff"]) == {
        "Appointment",
        "Patient",
        "Practitioner",
        "Location",
    }


def returns_an_operation_outcome_naming_the_rule_when_the_appointment_refusal_is_read(
    seed_environment: None,
) -> None:
    samples = _staff_samples()

    refusal = samples["Appointment-refusal-staff"]
    assert refusal["resourceType"] == "OperationOutcome"
    assert "violated-rule" in str(refusal["issue"])


def returns_refusals_that_are_outcomes_with_the_matching_code_when_samples_are_built(
    seed_environment: None,
) -> None:
    samples = _staff_samples()

    codes = {
        kind: samples[f"{kind}-refusal-staff"]["issue"][0]["code"]  # type: ignore[index]
        for kind in ("AppointmentResponse", "Communication", "AuditEvent")
    }
    assert codes == {
        "AppointmentResponse": "invalid",
        "Communication": "invalid",
        "AuditEvent": "forbidden",
    }
    assert "participantStatus" in str(samples["AppointmentResponse-refusal-staff"])


def returns_a_sample_per_status_and_kind_when_the_seed_serves_it(seed_environment: None) -> None:
    samples = _staff_samples()

    appointment_statuses = {
        name.removeprefix("Appointment-").removesuffix("-staff")
        for name in samples
        if name.startswith("Appointment-") and name.endswith("-staff")
    } & {"booked", "cancelled", "checked-in", "fulfilled", "noshow", "proposed", "waitlist"}
    assert appointment_statuses == {
        "booked",
        "cancelled",
        "checked-in",
        "fulfilled",
        "noshow",
        "proposed",
        "waitlist",
    }
    served_kinds = set(Notification.objects.values_list("kind", flat=True))
    assert served_kinds
    for kind in served_kinds & set(NOTIFICATION_KIND_WORDS):
        assert f"Communication-{kind.lower()}-staff" in samples


def returns_the_code_named_in_the_file_when_an_audit_action_sample_is_read(
    seed_environment: None,
) -> None:
    samples = _staff_samples()

    assert {"AuditEvent-action-C-staff", "AuditEvent-action-U-staff"} <= set(samples)
    for name, body in samples.items():
        if name.startswith("AuditEvent-action-"):
            code = name.removeprefix("AuditEvent-action-").removesuffix("-staff")
            assert body["action"] == code
