"""Section 14 schemas of the three hold endpoints. Strict: no patient id, no room id, no field the
visitor has no business setting."""

from collections.abc import Mapping
from datetime import date

from rest_framework import serializers

from scheduling.domain.visitor_rules import EMAIL_MAXIMUM
from scheduling.models import BookingHold
from scheduling.use_cases.booking_holds import HoldCommand
from scheduling.views.booking_schemas import (
    VISIT_REASON_MAXIMUM,
    OffsetDateTimeField,
    format_instant,
    required_instant,
    required_uuid,
    uuid_of,
)
from scheduling.views.schemas import (
    StrictCode,
    StrictEmail,
    StrictLine,
    StrictSerializer,
    StrictText,
)

NAME_MAXIMUM = 200
PHONE_MAXIMUM = 30
CODE_LENGTH = 6


class HoldRequest(StrictSerializer):
    appointment_type_id = serializers.UUIDField()
    clinician_id = serializers.UUIDField(required=False)
    starts_at = OffsetDateTimeField()
    full_name = StrictLine(max_length=NAME_MAXIMUM)
    date_of_birth = serializers.DateField()
    email = StrictEmail(max_length=EMAIL_MAXIMUM)
    phone = StrictLine(max_length=PHONE_MAXIMUM, allow_blank=True, required=False)
    reason = StrictText(max_length=VISIT_REASON_MAXIMUM, allow_blank=True, required=False)
    terms_accepted = serializers.BooleanField()


class ResendRequest(StrictSerializer):
    pass


class VerifyRequest(StrictSerializer):
    code = StrictCode(
        rf"^\d{{{CODE_LENGTH}}}$", error_messages={"invalid": "Enter the 6 digit code."}
    )


def hold_command_of(values: Mapping[str, object]) -> HoldCommand:
    birth_date = values["date_of_birth"]
    if not isinstance(birth_date, date):
        raise TypeError("date_of_birth passed its schema, so it is a date")
    return HoldCommand(
        appointment_type_id=required_uuid(values, "appointment_type_id"),
        clinician_id=uuid_of(values, "clinician_id"),
        starts_at=required_instant(values, "starts_at"),
        full_name=str(values["full_name"]),
        birth_date=birth_date,
        email=str(values["email"]),
        phone=str(values.get("phone", "")),
        reason=str(values.get("reason", "")),
        terms_accepted=values["terms_accepted"] is True,
    )


def hold_body(hold: BookingHold) -> dict[str, object]:
    return {
        "id": str(hold.pk),
        "appointment_type_id": str(hold.appointment_type_id),
        "clinician_id": str(hold.clinician_id),
        "starts_at": format_instant(hold.starts_at),
        "ends_at": format_instant(hold.ends_at),
        "expires_at": format_instant(hold.expires_at),
    }
