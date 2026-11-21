"""Section 6.6: the public detail of a provider, a hospital and a specialty. Read through the same
catalogue and slot search as the search, so a page never shows what search would not list."""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.search_availability import BookableType, shortest_type
from scheduling.domain.search_query import DEFAULT_PAGE_SIZE, parse_search_query
from scheduling.models import ClinicianProfile, Hospital, Specialty
from scheduling.use_cases.search import provider_results, search_public
from scheduling.use_cases.search_catalog import CatalogProvider, load_catalog
from scheduling.use_cases.search_types import ProviderResult, SearchPage, SpecialtyResult

PLAIN_QUERY = parse_search_query({})


@dataclass(frozen=True)
class ProviderDetail:
    provider: ProviderResult
    bio: str
    appointment_types: tuple[BookableType, ...]
    chosen_type: BookableType


@dataclass(frozen=True)
class Named:
    id: UUID
    name: str


@dataclass(frozen=True)
class FirstAvailableChoice:
    department_name: str
    appointment_type: BookableType


@dataclass(frozen=True)
class HospitalDetail:
    id: UUID
    name: str
    description: str
    street_address: str
    postal_code: str
    city: str
    country: str
    phone: str
    time_zone: str
    departments: list[Named]
    specialties: list[Named]
    first_available: list[FirstAvailableChoice]
    providers: list[ProviderResult]


@dataclass(frozen=True)
class SpecialtyDetail:
    specialty: SpecialtyResult
    providers: SearchPage[ProviderResult]


def load_provider_detail(
    provider_id: UUID, type_id: UUID | None, now: datetime
) -> Result[ProviderDetail]:
    catalog = load_catalog(provider_id=provider_id)
    if not catalog:
        return Failure.not_found()
    types = catalog[0].types
    chosen = next((item for item in types if item.id == type_id), None) or shortest_type(types)
    query = replace(PLAIN_QUERY, appointment_type_id=chosen.id)
    bio = ClinicianProfile.objects.values_list("bio", flat=True).get(pk=provider_id)
    return Success(ProviderDetail(provider_results(catalog, query, now)[0], bio, types, chosen))


def load_hospital_detail(hospital_id: UUID, now: datetime) -> Result[HospitalDetail]:
    row = (
        Hospital.objects.filter(pk=hospital_id, is_active=True)
        .values_list(
            "name",
            "description",
            "street_address",
            "postal_code",
            "city",
            "country",
            "phone",
            "time_zone",
        )
        .first()
    )
    if row is None:
        return Failure.not_found()
    catalog = load_catalog(hospital_id=hospital_id)
    return Success(
        HospitalDetail(
            hospital_id,
            *row,
            departments=_departments(catalog),
            specialties=_specialties(catalog),
            first_available=_first_available(catalog),
            providers=provider_results(catalog, PLAIN_QUERY, now),
        )
    )


def load_specialty_detail(
    specialty_id: UUID, page: int, now: datetime, page_size: int = DEFAULT_PAGE_SIZE
) -> Result[SpecialtyDetail]:
    row = (
        Specialty.objects.filter(pk=specialty_id, is_active=True)
        .values_list("name", "code")
        .first()
    )
    if row is None:
        return Failure.not_found()
    query = replace(PLAIN_QUERY, specialty_id=specialty_id, page=page, page_size=page_size)
    summary = search_public("specialties", replace(query, page=1), now).results
    if not summary and ClinicianProfile.objects.filter(specialty_id=specialty_id).exists():
        # Used, but by nobody search would list: as hidden as an inactive hospital's own page.
        return Failure.not_found()
    empty = SpecialtyResult(specialty_id, row[0], row[1], 0, 0, None, False)
    providers = search_public("providers", query, now)
    return Success(SpecialtyDetail(summary[0] if summary else empty, providers))


def _departments(catalog: list[CatalogProvider]) -> list[Named]:
    return _by_name({item.department_id: item.department_name for item in catalog})


def _specialties(catalog: list[CatalogProvider]) -> list[Named]:
    return _by_name({item.specialty_id: item.specialty_name for item in catalog})


def _by_name(names: dict[UUID, str]) -> list[Named]:
    return sorted(
        (Named(key, name) for key, name in names.items()), key=lambda item: item.name.casefold()
    )


def _first_available(catalog: list[CatalogProvider]) -> list[FirstAvailableChoice]:
    seen: dict[UUID, FirstAvailableChoice] = {}
    for provider in sorted(catalog, key=lambda item: item.department_name.casefold()):
        for kind in provider.types:
            seen.setdefault(kind.id, FirstAvailableChoice(provider.department_name, kind))
    return list(seen.values())
