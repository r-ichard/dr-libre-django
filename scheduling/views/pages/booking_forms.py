"""The visitor's details form and the patient's reason, read as a browser sends them."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from django.http import QueryDict
from rest_framework import serializers

from scheduling.domain.date_parts import BIRTH_PARTS, read_birth_date
from scheduling.domain.failure import Failure, Success
from scheduling.domain.profile_rules import phone_failure
from scheduling.domain.visitor_rules import EMAIL_MAXIMUM
from scheduling.use_cases.booking_holds import HoldCommand
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.booking_schemas import VISIT_REASON_MAXIMUM
from scheduling.views.hold_schemas import (
    NAME_MAXIMUM,
    PHONE_MAXIMUM,
    hold_command_of,
)
from scheduling.views.pages.booking_links import SlotRequest
from scheduling.views.schemas import StrictSerializer, validate_body

TERMS_MESSAGE = "Accept the terms and the privacy notice."
REASON_TOO_LONG = f"Keep the reason under {VISIT_REASON_MAXIMUM} characters."
REQUIRED_MESSAGES = {
    "full_name": "Enter your full name.",
    "email": "Enter your email address.",
}
TEXT_FIELDS = ("full_name", "email", "phone", "reason")
FIELD_ORDER = ("full_name", "date_of_birth", "email", "phone", "reason", "terms_accepted")


class DetailsSchema(StrictSerializer):
    full_name = serializers.CharField(max_length=NAME_MAXIMUM)
    date_of_birth = serializers.DateField(
        error_messages={"invalid": "Enter a valid date of birth."}
    )
    email = serializers.EmailField(
        max_length=EMAIL_MAXIMUM, error_messages={"invalid": "Enter a valid email address."}
    )
    phone = serializers.CharField(max_length=PHONE_MAXIMUM, allow_blank=True)
    reason = serializers.CharField(
        max_length=VISIT_REASON_MAXIMUM,
        allow_blank=True,
        error_messages={"max_length": REASON_TOO_LONG},
    )


class ReasonSchema(StrictSerializer):
    reason = serializers.CharField(
        max_length=VISIT_REASON_MAXIMUM,
        allow_blank=True,
        error_messages={"max_length": REASON_TOO_LONG},
    )


@dataclass
class DetailsForm:
    values: dict[str, str] = field(default_factory=dict)
    terms_accepted: bool = False
    field_errors: dict[str, str] = field(default_factory=dict)
    valid: Mapping[str, object] = field(default_factory=dict)

    @property
    def focus(self) -> dict[str, bool]:
        first = next((name for name in FIELD_ORDER if name in self.field_errors), None)
        return {first: True} if first else {}

    @property
    def summary(self) -> list[dict[str, str]]:
        return [
            {"target": self._target(name), "message": self.field_errors[name]}
            for name in FIELD_ORDER
            if name in self.field_errors
        ]

    def _target(self, name: str) -> str:
        if name != "date_of_birth":
            return f"id_{name}"
        first_bad = next((part for part in BIRTH_PARTS if not _is_number(self.values[part])), None)
        return f"id_{first_bad or BIRTH_PARTS[0]}"

    def add_failure(self, failure: Failure) -> None:
        for name, message in field_messages_of(failure):
            self.field_errors.setdefault(name, message)


def field_messages_of(failure: Failure) -> list[tuple[str, str]]:
    items = failure.details.get("fields")
    if not isinstance(items, list):
        return []
    return [(str(item["field"]), str(item["message"])) for item in items if isinstance(item, dict)]


def read_details(post: QueryDict) -> DetailsForm:
    values = {name: post.get(name, "").strip() for name in (*TEXT_FIELDS, *BIRTH_PARTS)}
    form = DetailsForm(values, terms_accepted=post.get("terms_accepted") is not None)
    day, month, year = (values[part] for part in BIRTH_PARTS)
    born = read_birth_date(day, month, year, _today(), required=True)
    if isinstance(born, Failure):
        form.add_failure(born)
    schema_input = {name: values[name] for name in TEXT_FIELDS}
    if isinstance(born, Success):
        schema_input["date_of_birth"] = str(born.value)
    checked = validate_body(DetailsSchema, schema_input)
    if isinstance(checked, Failure):
        form.add_failure(checked)
    else:
        form.valid = checked.value
    for name, message in REQUIRED_MESSAGES.items():
        if not values[name]:
            form.field_errors[name] = message
    if not form.terms_accepted:
        form.field_errors["terms_accepted"] = TERMS_MESSAGE
    _add_rule_failures(form)
    return form


def _add_rule_failures(form: DetailsForm) -> None:
    """The rules the hold use case applies too, so one answer lists every error, not one round
    of them after the next."""
    phone_problem = phone_failure(form.values["phone"])
    if phone_problem is not None:
        form.field_errors.setdefault("phone", phone_problem.message)


def _today() -> date:
    return current_request_context().now.date()


def _is_number(text: str) -> bool:
    return text.isascii() and text.isdigit()


def hold_command_from(form: DetailsForm, slot: SlotRequest) -> HoldCommand:
    return hold_command_of(
        {
            **form.valid,
            "appointment_type_id": slot.type_id,
            "clinician_id": slot.provider_id,
            "starts_at": slot.starts_at,
            "terms_accepted": True,
        }
    )


def reason_error(post: QueryDict) -> str:
    checked = validate_body(ReasonSchema, {"reason": post.get("reason", "").strip()})
    return REASON_TOO_LONG if isinstance(checked, Failure) else ""
