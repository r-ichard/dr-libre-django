"""Section 14 request schemas for login, logout and the sign-in link."""

from rest_framework import serializers

from scheduling.domain.visitor_rules import EMAIL_MAXIMUM, is_valid_email
from scheduling.views.schemas import (
    StrictEmail,
    StrictSecretLine,
    StrictSecretText,
    StrictSerializer,
)

PASSWORD_MAX_LENGTH = 1000
TOKEN_MAX_LENGTH = 200


class LoginRequest(StrictSerializer):
    email = StrictEmail(max_length=EMAIL_MAXIMUM)
    # Secret: a refusal never quotes it.
    # Not trimmed, and bounded so a huge body cannot make the hasher expensive.
    password = StrictSecretText(
        min_length=1, max_length=PASSWORD_MAX_LENGTH, trim_whitespace=False, write_only=True
    )

    def validate_email(self, value: str) -> str:
        lowered = value.lower()
        if not is_valid_email(lowered):
            raise serializers.ValidationError("Enter a valid email address.")
        return lowered


class LogoutRequest(StrictSerializer):
    pass


class LinkRequest(StrictSerializer):
    email = StrictEmail(max_length=EMAIL_MAXIMUM)

    validate_email = LoginRequest.validate_email


class LinkVerifyRequest(StrictSerializer):
    # Secret: a refusal never quotes it.
    token = StrictSecretLine(min_length=1, max_length=TOKEN_MAX_LENGTH, write_only=True)
