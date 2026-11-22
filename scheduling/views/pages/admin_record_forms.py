"""Section 10: an admin record form as a browser sends it. Text is read into typed values with
the domain checks; what was typed is kept as text so a refused form shows it again."""

from collections.abc import Callable, Mapping
from uuid import UUID
from zoneinfo import available_timezones

from django.db.models import Model
from django.http import QueryDict

from scheduling.domain import record_fields
from scheduling.domain.failure import Failure, Result
from scheduling.use_cases import admin_record_reads
from scheduling.views.pages.admin_record_kinds import (
    CHECKBOX,
    KIND_VIEWS,
    SELECT,
    FormField,
)
from scheduling.views.pages.local_time import errors_by_field

DESCRIPTION_LENGTH = 2000
BOOLEAN_FIELDS = ("is_active", "is_bookable_online", "needs_room")
Parser = Callable[[str], Result[object]]


def _text(field: str, label: str, maximum: int) -> Parser:
    return lambda raw: record_fields.check_text(field, raw, maximum, f"Enter {label}.")


def _time_zone(raw: str) -> Result[object]:
    return record_fields.check_time_zone(raw, available_timezones())


PARSERS: dict[str, Parser] = {
    "name": record_fields.check_name,
    "code": record_fields.check_code,
    "description": lambda raw: record_fields.check_text(
        "description", raw, DESCRIPTION_LENGTH, None
    ),
    "street_address": _text("street_address", "a street address", 200),
    "postal_code": _text("postal_code", "a postal code", 20),
    "city": _text("city", "a city", 100),
    "country": _text("country", "a country", 100),
    "phone": _text("phone", "a phone number", 30),
    "time_zone": _time_zone,
    "floor": _text("floor", "a floor", 20),
    "capacity": record_fields.check_capacity,
    "duration_minutes": record_fields.check_duration_minutes,
    "buffer_minutes": record_fields.check_buffer_minutes,
    "colour": record_fields.check_colour,
    "equipment": record_fields.check_equipment,
}
SELECT_MESSAGES = {"hospital": "Choose a hospital.", "department": "Choose a department."}


def typed_text(kind: str, post: QueryDict) -> dict[str, str]:
    """What was typed, for showing the form again: a checkbox is "on" or empty."""
    raw: dict[str, str] = {}
    for field in KIND_VIEWS[kind].fields:
        if field.widget == CHECKBOX:
            raw[field.name] = "on" if field.name in post else ""
        else:
            raw[field.name] = post.get(field.name, "")
    return raw


def initial_text(kind: str, row: Model | None) -> dict[str, str]:
    """A new record starts active, bookable and without buffer; an edit starts from the row."""
    shown: dict[str, str] = {}
    for field in KIND_VIEWS[kind].fields:
        if row is None:
            fresh = field.name in ("is_active", "is_bookable_online")
            shown[field.name] = "on" if fresh else ("0" if field.name == "buffer_minutes" else "")
        else:
            shown[field.name] = _stored_text(field, row)
    return shown


def _stored_text(field: FormField, row: Model) -> str:
    if field.widget == SELECT and field.name != "time_zone":
        return str(getattr(row, f"{field.name}_id"))
    value = getattr(row, field.name)
    if field.widget == CHECKBOX:
        return "on" if value else ""
    if field.name == "equipment":
        return "\n".join(value)
    return "" if value is None else str(value)


def parse_form(kind: str, typed: Mapping[str, str]) -> tuple[dict[str, object], dict[str, str]]:
    """Typed values for the use case, and the message of each field that cannot be read."""
    values: dict[str, object] = {}
    errors: dict[str, str] = {}
    for field in KIND_VIEWS[kind].fields:
        raw = typed[field.name]
        if field.name in ("latitude", "longitude"):
            continue
        if field.widget == CHECKBOX:
            values[field.name] = raw == "on"
        elif field.name in SELECT_MESSAGES:
            _read_parent(field.name, raw, values, errors)
        else:
            _read(field.name, PARSERS[field.name](raw), values, errors)
    if "latitude" in typed:
        _read_coordinates(typed, values, errors)
    return values, errors


def _read(
    name: str, result: Result[object], values: dict[str, object], errors: dict[str, str]
) -> None:
    if isinstance(result, Failure):
        for key, text in errors_by_field(result).items():
            errors.setdefault(key, text)
    else:
        values[name] = result.value


def _read_parent(name: str, raw: str, values: dict[str, object], errors: dict[str, str]) -> None:
    try:
        values[f"{name}_id"] = UUID(raw)
    except ValueError:
        errors[name] = SELECT_MESSAGES[name]


def _read_coordinates(
    typed: Mapping[str, str], values: dict[str, object], errors: dict[str, str]
) -> None:
    result = record_fields.check_coordinates(typed["latitude"], typed["longitude"])
    if isinstance(result, Failure):
        errors.update(errors_by_field(result))
    else:
        values["latitude"], values["longitude"] = result.value


def form_fields(
    kind: str, typed: dict[str, str], errors: dict[str, str]
) -> list[dict[str, object]]:
    shown: list[dict[str, object]] = []
    for field in KIND_VIEWS[kind].fields:
        item: dict[str, object] = {
            "name": field.name,
            "label": field.label,
            "widget": field.widget,
            "hint": field.hint,
            "value": typed[field.name],
            "checked": typed[field.name] == "on",
            "error": errors.get(field.name, ""),
        }
        if field.widget == SELECT:
            item["options"] = _options(kind, field.name)
        shown.append(item)
    return shown


def _options(kind: str, name: str) -> list[tuple[str, str]]:
    if name == "time_zone":
        zones = [(zone, zone) for zone in sorted(available_timezones())]
        return [("", "Choose a time zone"), *zones]
    return [("", f"Choose a {name}"), *admin_record_reads.parent_choices(kind)]
