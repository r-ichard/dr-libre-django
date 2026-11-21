"""Section 6.3: the choices a visitor can filter by. Read-only, public fields of the catalogue
only, so a choice that could never match is not offered."""

from dataclasses import dataclass
from uuid import UUID

from scheduling.use_cases.search_catalog import load_catalog


@dataclass(frozen=True)
class FilterOptions:
    specialties: list[tuple[UUID, str]]
    hospitals: list[tuple[UUID, str]]
    cities: list[str]
    appointment_types: list[tuple[UUID, str]]


def load_filter_options() -> FilterOptions:
    providers = load_catalog()
    return FilterOptions(
        specialties=sorted(
            {(item.specialty_id, item.specialty_name) for item in providers}, key=_name
        ),
        hospitals=sorted({(item.hospital_id, item.hospital_name) for item in providers}, key=_name),
        cities=sorted({item.city for item in providers}),
        appointment_types=sorted(
            {(kind.id, kind.name) for item in providers for kind in item.types}, key=_name
        ),
    )


def _name(choice: tuple[UUID, str]) -> str:
    return choice[1].casefold()
