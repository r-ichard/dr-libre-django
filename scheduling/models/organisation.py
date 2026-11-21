from django.contrib.postgres.fields import ArrayField
from django.db.models import (
    PROTECT,
    BooleanField,
    CharField,
    FloatField,
    ForeignKey,
    Q,
    SmallIntegerField,
    TextField,
    UniqueConstraint,
)

from scheduling.models.base import Versioned, at_least, between, check, not_blank

COLOUR_PATTERN = r"^#[0-9a-f]{6}$"


class Hospital(Versioned):
    fhir_resources = ("Organization", "Location")
    name = CharField(max_length=200)
    code = CharField(max_length=50)
    description = TextField(blank=True, default="")
    street_address = CharField(max_length=200)
    postal_code = CharField(max_length=20)
    city = CharField(max_length=100)
    country = CharField(max_length=100)
    phone = CharField(max_length=30)
    time_zone = CharField(max_length=64)
    latitude = FloatField(null=True, blank=True)
    longitude = FloatField(null=True, blank=True)
    is_active = BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["code"],
                name="hospital_code_unique",
                violation_error_message="code is taken",
            ),
            not_blank("hospital", "name"),
            not_blank("hospital", "code"),
            between("hospital", "latitude", -90, 90),
            between("hospital", "longitude", -180, 180),
            check(
                "hospital_coordinates_together",
                Q(latitude__isnull=True, longitude__isnull=True)
                | Q(latitude__isnull=False, longitude__isnull=False),
                "latitude and longitude are both set or both empty",
            ),
        ]


class Department(Versioned):
    fhir_resources = ("Organization",)
    hospital = ForeignKey(Hospital, on_delete=PROTECT)
    name = CharField(max_length=200)
    code = CharField(max_length=50)
    description = TextField(blank=True, default="")

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["code"],
                name="department_code_unique",
                violation_error_message="code is taken",
            ),
            not_blank("department", "name"),
            not_blank("department", "code"),
        ]


class Specialty(Versioned):
    fhir_resources = ("CodeSystem", "ValueSet")
    name = CharField(max_length=200)
    code = CharField(max_length=50)
    is_active = BooleanField(default=True)

    class Meta:
        verbose_name_plural = "specialties"
        constraints = [
            UniqueConstraint(
                fields=["code"],
                name="specialty_code_unique",
                violation_error_message="code is taken",
            ),
            not_blank("specialty", "name"),
            not_blank("specialty", "code"),
        ]


class Room(Versioned):
    fhir_resources = ("Location",)
    department = ForeignKey(Department, on_delete=PROTECT)
    name = CharField(max_length=200)
    code = CharField(max_length=50)
    floor = CharField(max_length=20)
    capacity = SmallIntegerField()
    equipment = ArrayField(CharField(max_length=100), default=list, blank=True)
    is_active = BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["code"], name="room_code_unique", violation_error_message="code is taken"
            ),
            not_blank("room", "name"),
            not_blank("room", "code"),
            at_least("room", "capacity", 1),
        ]


class AppointmentType(Versioned):
    fhir_resources = ("HealthcareService",)
    department = ForeignKey(Department, on_delete=PROTECT)
    name = CharField(max_length=200)
    code = CharField(max_length=50)
    duration_minutes = SmallIntegerField()
    needs_room = BooleanField(default=False)
    buffer_minutes = SmallIntegerField(default=0)
    colour = CharField(max_length=7)
    is_active = BooleanField(default=True)
    is_bookable_online = BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["code"],
                name="appointmenttype_code_unique",
                violation_error_message="code is taken",
            ),
            not_blank("appointmenttype", "name"),
            not_blank("appointmenttype", "code"),
            at_least("appointmenttype", "duration_minutes", 1),
            at_least("appointmenttype", "buffer_minutes", 0),
            check(
                "appointmenttype_colour_hex",
                Q(colour__regex=COLOUR_PATTERN),
                "colour must be a lower case #rrggbb value",
            ),
        ]
