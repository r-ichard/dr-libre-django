"""The visitor's details form and the patient's reason, read as a browser sends them."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from django.http import QueryDict
from rest_framework import serializers

from scheduling.domain.failure import Failure
from scheduling.domain.profile_rules import phone_failure
from scheduling.domain.visitor_rules import valid_birth_date
from scheduling.use_cases.booking_holds import HoldCommand
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.booking_schemas import VISIT_REASON_MAXIMUM
from scheduling.views.hold_schemas import (
    EMAIL_MAXIMUM,
    NAME_MAXIMUM,
    PHONE_MAXIMUM,
    hold_command_of,
)
from scheduling.views.pages.booking_links import SlotRequest
from scheduling.views.pages.portal_forms import day_or_none
from scheduling.views.schemas import StrictSerializer, validate_body

TERMS_MESSAGE = "Accept the terms and the privacy notice."
REASON_TOO_LONG = f"Keep the reason under {VISIT_REASON_MAXIMUM} characters."
REQUIRED_MESSAGES = {
    "full_name": "Enter your full name.",
    "date_of_birth": "Enter your date of birth.",
    "email": "Enter your email address.",
}
TEXT_FIELDS = ("full_name", "date_of_birth", "email", "phone", "reason")
FIELD_ORDER = (*TEXT_FIELDS, "terms_accepted")


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
            {"target": f"id_{name}", "message": self.field_errors[name]}
            for name in FIELD_ORDER
            if name in self.field_errors
        ]

    def add_failure(self, failure: Failure) -> None:
        for name, message in field_messages_of(failure):
            self.field_errors.setdefault(name, message)


def field_messages_of(failure: Failure) -> list[tuple[str, str]]:
    items = failure.details.get("fields")
    if not isinstance(items, list):
        return []
    return [(str(item["field"]), str(item["message"])) for item in items if isinstance(item, dict)]


def read_details(post: QueryDict) -> DetailsForm:
    values = {name: post.get(name, "").strip() for name in TEXT_FIELDS}
    form = DetailsForm(values, terms_accepted=post.get("terms_accepted") is not None)
    checked = validate_body(DetailsSchema, values)
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
    born = day_or_none(form.values["date_of_birth"])
    today = current_request_context().now.date()
    if born is not None and not valid_birth_date(born, today):
        form.field_errors.setdefault("date_of_birth", "Enter a valid date of birth.")
    phone_problem = phone_failure(form.values["phone"])
    if phone_problem is not None:
        form.field_errors.setdefault("phone", phone_problem.message)


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
