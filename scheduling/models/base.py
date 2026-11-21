from collections.abc import Iterable
from enum import StrEnum
from typing import ClassVar

from django.db import DatabaseError
from django.db.models import (
    PROTECT,
    CheckConstraint,
    DateTimeField,
    F,
    ForeignKey,
    Model,
    PositiveIntegerField,
    Q,
    UUIDField,
)
from django.db.models.base import ModelBase
from django.db.models.functions import ExtractSecond, Length, Lower
from django.db.models.lookups import Exact

from scheduling.identifiers import new_identifier


class Record(Model):
    """Section 3 preamble: opaque time-ordered id, UTC creation and update time, creator.
    The creator is empty for rows made by the system or by a visitor."""

    id = UUIDField(primary_key=True, default=new_identifier, editable=False)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    created_by = ForeignKey(
        "scheduling.User", null=True, blank=True, on_delete=PROTECT, related_name="+"
    )

    # Section 15: the FHIR resources a model maps to, or why it maps to none. Exactly one is set.
    fhir_resources: ClassVar[tuple[str, ...]] = ()
    fhir_not_exposed: ClassVar[str] = ""

    class Meta:
        abstract = True


class Versioned(Record):
    """Section 15.1: version starts at 1 and grows by one on every change. A database trigger
    (migration 0004) refuses any other write, so a stale save fails in the writing statement."""

    version = PositiveIntegerField(default=1)

    class Meta:
        abstract = True

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        loaded_version = self.version
        if not self._state.adding:
            self.version = loaded_version + 1
            if update_fields is not None:
                update_fields = {*update_fields, "version"}
        try:
            super().save(
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            )
        except DatabaseError:
            self.version = loaded_version
            raise


def check(name: str, condition: Q, message: str) -> CheckConstraint:
    return CheckConstraint(condition=condition, name=name, violation_error_message=message)


def not_blank(prefix: str, field: str) -> CheckConstraint:
    return check(f"{prefix}_{field}_not_blank", ~Q(**{field: ""}), f"{field} must not be empty")


def choices_of(enumeration: type[StrEnum]) -> list[tuple[str, str]]:
    # Same pairs TextChoices derives, so these enumerations moving out creates no migration.
    return [(member.value, member.name.replace("_", " ").title()) for member in enumeration]


def one_of(prefix: str, field: str, choices: type[StrEnum]) -> CheckConstraint:
    values = [member.value for member in choices]
    allowed = ", ".join(values)
    return check(
        f"{prefix}_{field}_listed",
        Q(**{f"{field}__in": values}),
        f"{field} must be one of {allowed}",
    )


def at_least(prefix: str, field: str, minimum: int) -> CheckConstraint:
    return check(
        f"{prefix}_{field}_at_least_{minimum}",
        Q(**{f"{field}__gte": minimum}),
        f"{field} must be at least {minimum}",
    )


def between(prefix: str, field: str, low: float, high: float) -> CheckConstraint:
    return check(
        f"{prefix}_{field}_between_{low}_and_{high}".replace(".", "_").replace("-", "minus_"),
        Q(**{f"{field}__gte": low, f"{field}__lte": high}),
        f"{field} must be from {low} to {high}",
    )


def ends_after_start(prefix: str, start: str, end: str) -> CheckConstraint:
    return check(
        f"{prefix}_{end}_after_{start}",
        Q(**{f"{end}__gt": F(start)}),
        f"{end} must be after {start}",
    )


def hash_is_64_characters(prefix: str, field: str) -> CheckConstraint:
    return check(
        f"{prefix}_{field}_64_characters",
        Q(Exact(Length(field), 64)),
        f"{field} must be exactly 64 characters",
    )


def lower_case(prefix: str, field: str) -> CheckConstraint:
    return check(
        f"{prefix}_{field}_lower_case", Q(**{field: Lower(field)}), f"{field} must be lower case"
    )


def whole_minutes(prefix: str, field: str) -> CheckConstraint:
    return check(
        f"{prefix}_{field}_whole_minutes",
        Q(Exact(ExtractSecond(field), 0)),
        f"{field} must be on a whole minute",
    )


def expires_after_creation(prefix: str) -> CheckConstraint:
    return check(
        f"{prefix}_expires_after_creation",
        Q(expires_at__gt=F("created_at")),
        "expires_at must be after created_at",
    )
