"""Section 6.2: exactly the columns a search result shows, and nothing else."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Opening:
    starts_at: datetime
    clinician_id: UUID
    appointment_type_id: UUID
    time_zone: str


@dataclass(frozen=True)
class ProviderResult:
    id: UUID
    full_name: str
    title: str
    specialty_id: UUID
    specialty_name: str
    hospital_id: UUID
    hospital_name: str
    city: str
    time_zone: str
    department_id: UUID
    department_name: str
    appointment_type_id: UUID
    appointment_type_name: str
    appointment_type_minutes: int
    next_starts: list[datetime]
    has_availability: bool


@dataclass(frozen=True)
class HospitalResult:
    id: UUID
    name: str
    street_address: str
    postal_code: str
    city: str
    country: str
    time_zone: str
    specialty_names: list[str]
    bookable_provider_count: int
    providers_with_availability_count: int
    earliest: Opening | None
    has_availability: bool

    @property
    def earliest_start(self) -> datetime | None:
        return None if self.earliest is None else self.earliest.starts_at


@dataclass(frozen=True)
class SpecialtyResult:
    id: UUID
    name: str
    provider_count: int
    hospital_count: int
    earliest: Opening | None
    has_availability: bool

    @property
    def earliest_start(self) -> datetime | None:
        return None if self.earliest is None else self.earliest.starts_at


type AnyResult = ProviderResult | HospitalResult | SpecialtyResult


@dataclass(frozen=True)
class SearchPage[Result: AnyResult]:
    results: Sequence[Result]
    total: int
    page: int
    page_count: int
    page_size: int
