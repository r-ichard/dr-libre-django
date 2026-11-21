"""doc/data-model.md is generated from the models; a stale copy fails here."""

import re
from pathlib import Path

import pytest
from django.apps import apps

DOCUMENT = Path(__file__).resolve().parent.parent / "doc" / "data-model.md"
REGENERATE = "python manage.py render_data_model"
EXPECTED_MODEL_COUNT = 18


def _rendered() -> str:
    from scheduling.data_model_document import render_data_model_document

    return render_data_model_document()


def returns_committed_document_when_rendered_from_models() -> None:
    rendered = _rendered()

    committed = DOCUMENT.read_text() if DOCUMENT.exists() else ""
    assert committed == rendered, f"doc/data-model.md is stale: run `{REGENERATE}`"


def returns_every_model_when_document_is_rendered() -> None:
    models = list(apps.get_app_config("scheduling").get_models())
    rendered = _rendered()

    assert len(models) == EXPECTED_MODEL_COUNT
    assert [m.__name__ for m in models if f"## {m.__name__}\n" not in rendered] == []


def returns_every_constraint_name_when_document_is_rendered() -> None:
    constraints = [
        constraint.name
        for model in apps.get_app_config("scheduling").get_models()
        for constraint in model._meta.constraints
    ]
    rendered = _rendered()

    assert len(constraints) > 50
    assert [name for name in constraints if f"`{name}`" not in rendered] == []


def returns_mermaid_relationship_when_foreign_key_exists() -> None:
    rendered = _rendered()

    assert "```mermaid\nerDiagram" in rendered
    assert re.search(r"Hospital \|\|--o\{ Department", rendered)
    assert re.search(r"Department \|\|--o\{ ClinicianProfile", rendered)
    assert re.search(r"User \|\|--o\| ClinicianProfile", rendered)


def returns_every_field_of_a_model_when_document_is_rendered() -> None:
    model = apps.get_model("scheduling", "Appointment")
    rendered = _rendered()

    field_names = [field.name for field in model._meta.concrete_fields]
    assert "starts_at" in field_names
    assert [name for name in field_names if f"`{name}`" not in rendered] == []


def returns_fhir_line_per_model_when_document_is_rendered() -> None:
    rendered = _rendered()

    hospital = rendered.split("## Hospital\n", 1)[1].split("\n## ", 1)[0]
    assert "FHIR: Organization, Location" in hospital
    waitlist = rendered.split("## WaitlistEntry\n", 1)[1].split("\n## ", 1)[0]
    assert "FHIR: Appointment, AppointmentResponse" in waitlist
    session = rendered.split("## Session\n", 1)[1].split("\n## ", 1)[0]
    assert "FHIR: not exposed" in session


def returns_exactly_one_fhir_declaration_when_every_model_is_walked() -> None:
    models = apps.get_app_config("scheduling").get_models()

    wrong = [
        model.__name__
        for model in models
        if bool(getattr(model, "fhir_resources", ()))
        == bool(getattr(model, "fhir_not_exposed", ""))
    ]

    assert wrong == []


def rejects_model_when_it_declares_neither_fhir_resource_nor_reason() -> None:
    from scheduling.data_model_document import check_fhir_declaration

    class Neither:
        fhir_resources: tuple[str, ...] = ()
        fhir_not_exposed = ""

    with pytest.raises(ValueError, match="Neither"):
        check_fhir_declaration(Neither)


def rejects_model_when_it_declares_both() -> None:
    from scheduling.data_model_document import check_fhir_declaration

    class Both:
        fhir_resources = ("Patient",)
        fhir_not_exposed = "credentials"

    with pytest.raises(ValueError, match="Both"):
        check_fhir_declaration(Both)
