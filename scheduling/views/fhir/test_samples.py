"""Task 22a, point 3: every sample /fhir can answer is free of empty arrays, objects, strings and
nulls, the rule the HL7 validator enforces in `make fhir-validate`."""

import pytest
from django.utils import timezone

from scheduling.demo_seed.seed_support import run_seed, seed_environment
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_declaration import FHIR_RESOURCES
from scheduling.domain.request_context import RequestContext
from scheduling.models import User
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
