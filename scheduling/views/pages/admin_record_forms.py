"""Section 10: an admin record form as a browser sends it. Text is read into typed values with
the domain checks; what was typed is kept as text so a refused form shows it again."""

from collections.abc import Callable, Mapping, Sequence
from uuid import UUID
from zoneinfo import available_timezones

from django.db.models import Model
from django.http import QueryDict

from scheduling.domain import clinician_rules, record_fields, user_rules
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.record_conflict import ReadKnown, ReadUnknown, ReadValue
from scheduling.domain.vocabulary import Role
from scheduling.use_cases import admin_record_reads
from scheduling.views.pages.admin_record_kinds import (
    CHECKBOX,
    PASSWORD,
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
    "full_name": _text("full_name", "a name", 200),
    "email": user_rules.check_email,
    "password": user_rules.check_password,
    "title": clinician_rules.check_title,
    "bio": lambda raw: record_fields.check_text("bio", raw, 2000, None),
    "round_robin_weight": clinician_rules.check_weight,
    "role": lambda raw: _role(raw),
}
SELECT_MESSAGES = {
    "hospital": "Choose a hospital.",
    "department": "Choose a department.",
    "user": "Choose a clinician user.",
    "specialty": "Choose a specialty.",
}
OPTIONAL_SELECTS = ("default_room",)
PLAIN_SELECTS = ("time_zone", "role")


def _role(raw: str) -> Result[object]:
    try:
        return Success(Role(raw).value)
    except ValueError:
        return Failure.invalid_input([FieldMessage("role", "Choose a role.")])


def typed_text(fields: Sequence[FormField], post: QueryDict) -> dict[str, str]:
    """What was typed, for showing the form again: a checkbox is "on" or empty. A password is
    read for the use case but never kept for the page."""
    raw: dict[str, str] = {}
    for field in fields:
        if field.widget == CHECKBOX:
            raw[field.name] = "on" if field.name in post else ""
        else:
            raw[field.name] = post.get(field.name, "")
    return raw


def kept_text(typed: Mapping[str, str]) -> dict[str, str]:
    return {name: ("" if name == "password" else text) for name, text in typed.items()}


def initial_text(fields: Sequence[FormField], row: Model | None) -> dict[str, str]:
    """A new record starts active, bookable and without buffer; an edit starts from the row."""
    shown: dict[str, str] = {}
    for field in fields:
        if row is None:
            fresh = field.name in ("is_active", "is_bookable_online")
            default = {"buffer_minutes": "0", "round_robin_weight": "1"}.get(field.name, "")
            shown[field.name] = "on" if fresh else default
        else:
            shown[field.name] = _stored_text(field, row)
    return shown


def _stored_text(field: FormField, row: Model) -> str:
    if field.widget == PASSWORD:
        return ""
    if field.widget == SELECT and field.name not in PLAIN_SELECTS:
        stored = getattr(row, f"{field.name}_id")
        return "" if stored is None else str(stored)
    value = getattr(row, field.name)
    if field.widget == CHECKBOX:
        return "on" if value else ""
    if field.name == "equipment":
        return "\n".join(value)
    return "" if value is None else str(value)


def parse_form(
    fields: Sequence[FormField], typed: Mapping[str, str]
) -> tuple[dict[str, object], dict[str, str]]:
    """Typed values for the use case, and the message of each field that cannot be read."""
    values: dict[str, object] = {}
    errors: dict[str, str] = {}
    for field in fields:
        raw = typed[field.name]
        if field.name in ("latitude", "longitude"):
            continue
        if field.widget == CHECKBOX:
            values[field.name] = raw == "on"
        elif field.name in OPTIONAL_SELECTS:
            _read_optional(field.name, raw, values, errors)
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
        errors[name] = SELECT_MESSAGES.get(name, f"Choose a {name.replace('_', ' ')}.")


def _read_optional(name: str, raw: str, values: dict[str, object], errors: dict[str, str]) -> None:
    if not raw:
        values[f"{name}_id"] = None
    else:
        _read_parent(name, raw, values, errors)


def _read_coordinates(
    typed: Mapping[str, str], values: dict[str, object], errors: dict[str, str]
) -> None:
    result = record_fields.check_coordinates(typed["latitude"], typed["longitude"])
    if isinstance(result, Failure):
        errors.update(errors_by_field(result))
    else:
        values["latitude"], values["longitude"] = result.value


def form_fields(
    kind: str, fields: Sequence[FormField], typed: dict[str, str], errors: dict[str, str]
) -> list[dict[str, object]]:
    shown: list[dict[str, object]] = []
    for field in fields:
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
    prompt = (
        ("", "None") if name in OPTIONAL_SELECTS else ("", f"Choose a {name.replace('_', ' ')}")
    )
    return [prompt, *_choices(kind, name)]


def _choices(kind: str, name: str) -> list[tuple[str, str]]:
    match name:
        case "role":
            return admin_record_reads.role_choices()
        case "user":
            return admin_record_reads.clinician_user_choices()
        case "specialty":
            return admin_record_reads.specialty_choices()
        case "default_room":
            return admin_record_reads.room_choices()
        case _:
            return admin_record_reads.parent_choices(kind)


def read_texts(fields: Sequence[FormField], post: QueryDict) -> dict[str, ReadValue]:
    """What the admin read when the form was opened: a `read_<field>` key is known text, a missing
    key (older tab, hand-made post) is unknown. Display only; never written, never authorization."""
    return {
        field.name: ReadKnown(post.get(f"read_{field.name}", ""))
        if f"read_{field.name}" in post
        else ReadUnknown()
        for field in fields
    }
