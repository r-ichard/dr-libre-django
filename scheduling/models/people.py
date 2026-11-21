from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import (
    PROTECT,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    EmailField,
    ForeignKey,
    OneToOneField,
    Q,
    SmallIntegerField,
    TextField,
    UniqueConstraint,
)

from scheduling.domain.vocabulary import Role
from scheduling.models.base import (
    Versioned,
    at_least,
    check,
    choices_of,
    lower_case,
    not_blank,
    one_of,
)
from scheduling.models.organisation import Department, Room, Specialty

UNUSABLE_PASSWORD_PREFIX = "!"  # noqa: S105


class User(AbstractBaseUser, Versioned):
    fhir_resources = ("Practitioner", "Patient")
    email = EmailField(max_length=254)
    full_name = CharField(max_length=200)
    role = CharField(max_length=20, choices=choices_of(Role))
    is_active = BooleanField(default=True)
    phone = CharField(max_length=30, blank=True, default="")
    date_of_birth = DateField(null=True, blank=True)
    email_verified_at = DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["email"], name="user_email_unique", violation_error_message="email is taken"
            ),
            lower_case("user", "email"),
            not_blank("user", "email"),
            not_blank("user", "full_name"),
            one_of("user", "role", Role),
            check(
                "user_only_patient_without_password",
                Q(role=Role.PATIENT) | ~Q(password__startswith=UNUSABLE_PASSWORD_PREFIX),
                "only a patient may have no usable password",
            ),
            check(
                "user_passwordless_has_verified_email",
                ~Q(password__startswith=UNUSABLE_PASSWORD_PREFIX)
                | Q(email_verified_at__isnull=False),
                "a patient without a password has a verified email",
            ),
        ]


class ClinicianProfile(Versioned):
    fhir_resources = ("PractitionerRole",)
    user = OneToOneField(User, on_delete=PROTECT)
    department = ForeignKey(Department, on_delete=PROTECT)
    specialty = ForeignKey(Specialty, on_delete=PROTECT)
    title = CharField(max_length=50)
    bio = TextField(blank=True, default="")
    default_room = ForeignKey(Room, null=True, blank=True, on_delete=PROTECT)
    round_robin_weight = SmallIntegerField(default=1)
    last_assigned_at = DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [at_least("clinicianprofile", "round_robin_weight", 1)]
