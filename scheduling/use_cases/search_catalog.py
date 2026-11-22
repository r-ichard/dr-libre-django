"""Section 6.1: the public catalogue, read through explicit field lists only, so a column
added to a model can never reach a search result by default."""

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from django.db.models import QuerySet

from scheduling.domain.search_availability import BookableType
from scheduling.models import AppointmentType, ClinicianProfile


@dataclass(frozen=True)
class CatalogProvider:
    id: UUID
    full_name: str
    title: str
    specialty_id: UUID
    specialty_name: str
    department_id: UUID
    department_name: str
    hospital_id: UUID
    hospital_name: str
    street_address: str
    postal_code: str
    city: str
    country: str
    time_zone: str
    latitude: float | None
    longitude: float | None
    specialty_code: str
    types: tuple[BookableType, ...]


def bookable_types() -> QuerySet[AppointmentType]:
    """The one rule for which types a caller without a session may see (also used by FHIR)."""
    return AppointmentType.objects.filter(is_active=True, is_bookable_online=True)


def listable_profiles(department_ids: Iterable[UUID]) -> QuerySet[ClinicianProfile]:
    """The one rule for which clinicians a caller without a session may see (also used by FHIR)."""
    return ClinicianProfile.objects.filter(
        user__is_active=True,
        specialty__is_active=True,
        department__hospital__is_active=True,
        department_id__in=department_ids,
    )


def load_catalog(
    *,
    provider_id: UUID | None = None,
    hospital_id: UUID | None = None,
    specialty_id: UUID | None = None,
) -> list[CatalogProvider]:
    """Two queries: listable clinicians, then the bookable types of their departments."""
    types_by_department: dict[UUID, list[BookableType]] = {}
    bookable = bookable_types().values_list(
        "id", "department_id", "name", "duration_minutes", "buffer_minutes"
    )
    for type_id, department_id, name, minutes, buffer in bookable:
        types_by_department.setdefault(department_id, []).append(
            BookableType(type_id, name, minutes, buffer)
        )
    listable = listable_profiles(list(types_by_department))
    for column, wanted in (
        ("pk", provider_id),
        ("department__hospital_id", hospital_id),
        ("specialty_id", specialty_id),
    ):
        if wanted is not None:
            listable = listable.filter(**{column: wanted})
    rows = listable.values_list(
        "id",
        "user__full_name",
        "title",
        "specialty_id",
        "specialty__name",
        "department_id",
        "department__name",
        "department__hospital_id",
        "department__hospital__name",
        "department__hospital__street_address",
        "department__hospital__postal_code",
        "department__hospital__city",
        "department__hospital__country",
        "department__hospital__time_zone",
        "department__hospital__latitude",
        "department__hospital__longitude",
        "specialty__code",
    )
    return [CatalogProvider(*row, tuple(types_by_department[row[5]])) for row in rows]
