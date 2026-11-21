"""Section 14 request schemas for login, logout and the sign-in link."""

from rest_framework import serializers

from scheduling.domain.audit_metadata import email_domain
from scheduling.views.schemas import StrictSerializer

EMAIL_MAX_LENGTH = 254
PASSWORD_MAX_LENGTH = 1000
TOKEN_MAX_LENGTH = 200


class LoginRequest(StrictSerializer):
    email = serializers.EmailField(max_length=EMAIL_MAX_LENGTH)
    # Not trimmed, and bounded so a huge body cannot make the hasher expensive.
    password = serializers.CharField(
        min_length=1, max_length=PASSWORD_MAX_LENGTH, trim_whitespace=False, write_only=True
    )

    def validate_email(self, value: str) -> str:
        lowered = value.lower()
        try:
            email_domain(lowered)
        except ValueError as refused:
            raise serializers.ValidationError("Enter a valid email address.") from refused
        return lowered


class LogoutRequest(StrictSerializer):
    pass


class LinkRequest(StrictSerializer):
    email = serializers.EmailField(max_length=EMAIL_MAX_LENGTH)

    validate_email = LoginRequest.validate_email


class LinkVerifyRequest(StrictSerializer):
    token = serializers.CharField(min_length=1, max_length=TOKEN_MAX_LENGTH, write_only=True)
