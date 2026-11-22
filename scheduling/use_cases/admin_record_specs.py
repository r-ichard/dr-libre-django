"""Section 10: what the five admin records share (fields, parent) and what each adds. One table
drives the generic create, update and delete use cases and the pages."""

from dataclasses import dataclass

from django.db.models import Model, QuerySet

from scheduling.models import (
    AppointmentType,
    ClinicianProfile,
    Department,
    Hospital,
    Room,
    Specialty,
    User,
)

CODE_TAKEN = "Code is taken."
DEPENDENT_WORDS = {
    "departments": ("department", "departments"),
    "clinicians": ("clinician", "clinicians"),
    "rooms": ("room", "rooms"),
    "appointment_types": ("appointment type", "appointment types"),
    "appointments": ("appointment", "appointments"),
    "availability_rules": ("availability rule", "availability rules"),
    "default_room_clinicians": (
        "clinician with this default room",
        "clinicians with this default room",
    ),
    "waitlist_entries": ("waitlist entry", "waitlist entries"),
    "appointments_as_patient": ("appointment as a patient", "appointments as a patient"),
    "appointments_as_clinician": ("appointment as a clinician", "appointments as a clinician"),
    "audit_entries": ("audit entry", "audit entries"),
    "clinician_profile": ("clinician profile", "clinician profiles"),
}


@dataclass(frozen=True)
class RecordSpec:
    kind: str
    model: type[Model]
    fields: tuple[str, ...]
    parent_field: str = ""
    parent_model: type[Model] | None = None
    search_fields: tuple[str, ...] = ("name", "code")
    order_by: tuple[str, ...] = ("name", "id")
    related: tuple[str, ...] = ()

    @property
    def select_related(self) -> tuple[str, ...]:
        return self.related or ((self.parent_form_name,) if self.parent_field else ())

    @property
    def parent_form_name(self) -> str:
        return self.parent_field.removesuffix("_id")

    @property
    def code_constraint(self) -> str:
        return f"{self.model._meta.model_name}_code_unique"

    def all_rows(self) -> QuerySet[Model]:
        return self.model._default_manager.all()


NAMED = ("name", "code")
SPECS = {
    spec.kind: spec
    for spec in (
        RecordSpec(
            "hospital",
            Hospital,
            (
                *NAMED,
                "description",
                "street_address",
                "postal_code",
                "city",
                "country",
                "phone",
                "time_zone",
                "latitude",
                "longitude",
                "is_active",
            ),
        ),  # fmt: skip
        RecordSpec("specialty", Specialty, (*NAMED, "is_active")),
        RecordSpec(
            "department",
            Department,
            (*NAMED, "description", "hospital_id"),
            "hospital_id",
            Hospital,
        ),
        RecordSpec(
            "room",
            Room,
            (*NAMED, "floor", "capacity", "equipment", "is_active", "department_id"),
            "department_id",
            Department,
        ),
        RecordSpec(
            "appointment_type",
            AppointmentType,
            (
                *NAMED,
                "duration_minutes",
                "needs_room",
                "buffer_minutes",
                "colour",
                "is_active",
                "is_bookable_online",
                "department_id",
            ),
            "department_id",
            Department,
        ),  # fmt: skip
        RecordSpec(
            "user",
            User,
            ("full_name", "email", "role", "is_active"),
            search_fields=("full_name", "email"),
            order_by=("full_name", "id"),
        ),
        RecordSpec(
            "clinician",
            ClinicianProfile,
            ("title", "bio", "round_robin_weight", "department_id"),
            "department_id",
            Department,
            search_fields=("user__full_name", "user__email", "title"),
            order_by=("user__full_name", "id"),
            related=("user", "department", "specialty", "default_room"),
        ),
    )
}


def count_text(count: int, reason: str) -> str:
    singular, plural = DEPENDENT_WORDS[reason]
    return f"{count} {singular if count == 1 else plural}"
