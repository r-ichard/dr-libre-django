from __future__ import annotations

from django.apps import apps
from django.contrib.postgres.constraints import ExclusionConstraint
from django.db.models import (
    BaseConstraint,
    Field,
    ForeignKey,
    Model,
    OneToOneField,
    UniqueConstraint,
)

HEADER = "\n".join(
    [
        "# Data model",
        "",
        "Generated from the models by `python manage.py render_data_model`; a test fails when",
        "this file is stale. Do not edit by hand.",
        "",
        "Every identifier is a UUIDv7 (ADR 0002). Every model also carries `created_at`,",
        "`updated_at` and `created_by` (a User; empty when the system or a visitor made the row).",
        "No relation cascades: deleting a referenced row fails in the database.",
        "",
    ]
)


def render_data_model_document() -> str:
    models = sorted(apps.get_app_config("scheduling").get_models(), key=lambda m: m.__name__)
    sections = [HEADER, _diagram(models)]
    sections += [_model_section(model) for model in models]
    return "\n".join(sections)


def _diagram(models: list[type[Model]]) -> str:
    lines = ["## Relationships", "", "```mermaid", "erDiagram"]
    for model in models:
        for field in model._meta.concrete_fields:
            if isinstance(field, ForeignKey) and field.name != "created_by":
                lines.append(_relationship(model, field))
    lines += ["```", ""]
    return "\n".join(lines)


def _relationship(model: type[Model], field: ForeignKey[Model]) -> str:
    parent = field.related_model.__name__
    optional_parent = "|o--o{" if field.null else "||--o{"
    arrow = "||--o|" if isinstance(field, OneToOneField) else optional_parent
    return f'    {parent} {arrow} {model.__name__} : "{field.name}"'


def check_fhir_declaration(model: type) -> None:
    """Section 15: a model names the FHIR resources it maps to, or says why it maps to none."""
    resources = getattr(model, "fhir_resources", ())
    reason = getattr(model, "fhir_not_exposed", "")
    if bool(resources) == bool(reason):
        raise ValueError(
            f"{model.__name__} must declare fhir_resources or fhir_not_exposed, and not both"
        )


def _fhir_line(model: type[Model]) -> str:
    check_fhir_declaration(model)
    resources = getattr(model, "fhir_resources", ())
    if resources:
        return "FHIR: " + ", ".join(resources)
    return f"FHIR: not exposed, {getattr(model, 'fhir_not_exposed', '')}"


def _model_section(model: type[Model]) -> str:
    lines = [f"## {model.__name__}", "", f"Table `{model._meta.db_table}`.", ""]
    lines += [_fhir_line(model), ""]
    lines += ["| Field | Type | Null | Rule |", "| --- | --- | --- | --- |"]
    lines += [_field_row(field) for field in model._meta.concrete_fields]
    lines += ["", "Constraints:", ""]
    constraints = sorted(model._meta.constraints, key=lambda constraint: constraint.name)
    lines += [_constraint_line(constraint) for constraint in constraints]
    if not constraints:
        lines.append("- none beyond the field rules above")
    lines.append("")
    return "\n".join(lines)


def _field_row(field: Field[object, object]) -> str:
    notes = []
    if field.primary_key:
        notes.append("primary key")
    elif field.unique:
        notes.append("unique")
    if field.max_length:
        notes.append(f"at most {field.max_length} characters")
    if isinstance(field, ForeignKey):
        notes.append(f"refers to {field.related_model.__name__}, protected")
    if field.choices:
        notes.append("one of " + ", ".join(str(value) for value, _ in field.flatchoices))
    null = "yes" if field.null else "no"
    return f"| `{field.name}` | {field.get_internal_type()} | {null} | {'; '.join(notes)} |"


def _constraint_line(constraint: BaseConstraint) -> str:
    return (
        f"- `{constraint.name}` ({_kind(constraint)}): {constraint.get_violation_error_message()}"
    )


def _kind(constraint: BaseConstraint) -> str:
    if isinstance(constraint, ExclusionConstraint):
        return "exclusion"
    if isinstance(constraint, UniqueConstraint):
        return "unique" if constraint.condition is None else "partial unique"
    return "check"
