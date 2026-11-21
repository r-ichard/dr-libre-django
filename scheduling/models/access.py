from django.db.models import (
    PROTECT,
    CharField,
    DateField,
    DateTimeField,
    EmailField,
    ForeignKey,
    SmallIntegerField,
    TextChoices,
    TextField,
    UniqueConstraint,
)

from scheduling.models.base import (
    Record,
    Versioned,
    at_least,
    ends_after_start,
    expires_after_creation,
    hash_is_64_characters,
    lower_case,
    one_of,
)
from scheduling.models.booking import AppointmentSource
from scheduling.models.organisation import AppointmentType
from scheduling.models.people import ClinicianProfile, User

HASH_LENGTH = 64


class CodePurpose(TextChoices):
    BOOKING = "BOOKING"


class HoldSource(TextChoices):
    ONLINE = AppointmentSource.ONLINE.value
    ROUND_ROBIN = AppointmentSource.ROUND_ROBIN.value


class Session(Record):
    fhir_not_exposed = "credential, never served; sign-in events are AuditEvent"
    user = ForeignKey(User, on_delete=PROTECT)
    token_hash = CharField(max_length=HASH_LENGTH)
    expires_at = DateTimeField()
    user_agent = CharField(max_length=300, blank=True, default="")

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["token_hash"],
                name="session_token_hash_unique",
                violation_error_message="token_hash is taken",
            ),
            hash_is_64_characters("session", "token_hash"),
            expires_after_creation("session"),
        ]


class BookingHold(Versioned):
    fhir_resources = ("Appointment",)
    clinician = ForeignKey(ClinicianProfile, on_delete=PROTECT)
    appointment_type = ForeignKey(AppointmentType, on_delete=PROTECT)
    starts_at = DateTimeField()
    ends_at = DateTimeField()
    source = CharField(max_length=20, choices=HoldSource)
    visitor_name = CharField(max_length=200)
    visitor_birth_date = DateField()
    visitor_email = EmailField(max_length=254)
    visitor_phone = CharField(max_length=30)
    visitor_reason = TextField(blank=True, default="")
    expires_at = DateTimeField()

    class Meta:
        constraints = [
            ends_after_start("bookinghold", "starts_at", "ends_at"),
            expires_after_creation("bookinghold"),
            lower_case("bookinghold", "visitor_email"),
            one_of("bookinghold", "source", HoldSource),
        ]


class VerificationCode(Record):
    fhir_not_exposed = "credential, never served; sign-in events are AuditEvent"
    code_hash = CharField(max_length=HASH_LENGTH)
    email = EmailField(max_length=254)
    purpose = CharField(max_length=20, choices=CodePurpose)
    expires_at = DateTimeField()
    attempts_used = SmallIntegerField(default=0)

    class Meta:
        constraints = [
            hash_is_64_characters("verificationcode", "code_hash"),
            lower_case("verificationcode", "email"),
            one_of("verificationcode", "purpose", CodePurpose),
            at_least("verificationcode", "attempts_used", 0),
            expires_after_creation("verificationcode"),
        ]


class SignInLink(Record):
    fhir_not_exposed = "credential, never served; sign-in events are AuditEvent"
    token_hash = CharField(max_length=HASH_LENGTH)
    patient = ForeignKey(User, on_delete=PROTECT)
    expires_at = DateTimeField()
    used_at = DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["token_hash"],
                name="signinlink_token_hash_unique",
                violation_error_message="token_hash is taken",
            ),
            hash_is_64_characters("signinlink", "token_hash"),
            expires_after_creation("signinlink"),
        ]
