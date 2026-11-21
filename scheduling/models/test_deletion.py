"""Section 10 "Deleting": no relation cascades; the database refuses to delete a referenced row."""

from collections.abc import Callable

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import PROTECT, Model, ProtectedError

from scheduling.models.builders import field_of, make, model_class

pytestmark = pytest.mark.django_db

MODEL_NAMES = {
    "Hospital", "Department", "Specialty", "User", "ClinicianProfile", "Room",
    "AppointmentType", "AvailabilityRule", "TimeOff", "Appointment", "WaitlistEntry",
    "Notification", "AuditLogEntry", "Session", "BookingHold", "VerificationCode", "SignInLink",
    "SignInFailure", "RateLimitHit",
}  # fmt: skip


REFERENCES: list[tuple[str, str, Callable[[], dict[str, object]]]] = [
    ("Hospital", "created_by", lambda: {"created_by": make("User")}),
    ("Department", "hospital", dict),
    ("ClinicianProfile", "user", dict),
    ("ClinicianProfile", "department", dict),
    ("ClinicianProfile", "specialty", dict),
    ("ClinicianProfile", "default_room", lambda: {"default_room": make("Room")}),
    ("Room", "department", dict),
    ("AppointmentType", "department", dict),
    ("AvailabilityRule", "clinician", dict),
    ("AvailabilityRule", "room", lambda: {"room": make("Room")}),
    ("TimeOff", "clinician", dict),
    ("Appointment", "patient", dict),
    ("Appointment", "clinician", dict),
    ("Appointment", "appointment_type", dict),
    ("Appointment", "room", lambda: {"room": make("Room")}),
    ("WaitlistEntry", "patient", dict),
    ("WaitlistEntry", "appointment_type", dict),
    (
        "WaitlistEntry",
        "preferred_clinician",
        lambda: {"preferred_clinician": make("ClinicianProfile")},
    ),
    (
        "WaitlistEntry",
        "offered_appointment",
        lambda: {"status": "OFFERED", "offered_appointment": make("Appointment")},
    ),
    ("Notification", "recipient", dict),
    ("Notification", "appointment", lambda: {"appointment": make("Appointment")}),
    ("AuditLogEntry", "actor", lambda: {"actor": make("User")}),
    ("Session", "user", dict),
    ("BookingHold", "clinician", dict),
    ("BookingHold", "appointment_type", dict),
    ("SignInLink", "patient", dict),
]  # fmt: skip


def _referenced_row(child: Model, field_name: str) -> Model:
    referenced = field_of(child, field_name)
    assert isinstance(referenced, Model)
    return referenced


@pytest.mark.parametrize(
    ("child_name", "field_name", "extra"),
    [pytest.param(c, f, e, id=f"{c}.{f}") for c, f, e in REFERENCES],
)
def rejects_delete_when_the_orm_deletes_a_referenced_row(
    child_name: str, field_name: str, extra: Callable[[], dict[str, object]]
) -> None:
    child = make(child_name, **extra())
    parent = _referenced_row(child, field_name)

    with pytest.raises(ProtectedError), transaction.atomic():
        parent.delete()


@pytest.mark.parametrize(
    ("child_name", "field_name", "extra"),
    [pytest.param(c, f, e, id=f"{c}.{f}") for c, f, e in REFERENCES],
)
def rejects_delete_when_raw_sql_deletes_a_referenced_row(
    child_name: str, field_name: str, extra: Callable[[], dict[str, object]]
) -> None:
    child = make(child_name, **extra())
    parent = _referenced_row(child, field_name)
    table = connection.ops.quote_name(parent._meta.db_table)

    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {table} WHERE id = %s", [parent.pk])  # noqa: S608
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def returns_deleted_row_when_nothing_refers_to_it() -> None:
    hospital = make("Hospital")

    hospital.delete()

    assert not model_class("Hospital")._default_manager.filter(pk=hospital.pk).exists()


def returns_exactly_the_nineteen_models_when_the_app_is_inspected() -> None:
    from django.apps import apps

    names = {model.__name__ for model in apps.get_app_config("scheduling").get_models()}

    assert names == MODEL_NAMES


def returns_protect_on_delete_when_every_foreign_key_is_inspected() -> None:
    from django.apps import apps
    from django.db.models import ForeignKey, OneToOneField

    relations = [
        field
        for model in apps.get_app_config("scheduling").get_models()
        for field in model._meta.get_fields()
        if isinstance(field, ForeignKey | OneToOneField)
    ]

    assert len(relations) >= len(REFERENCES)
    assert [f.name for f in relations if f.remote_field.on_delete is not PROTECT] == []
