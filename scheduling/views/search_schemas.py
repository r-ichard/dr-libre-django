"""Section 14 GET /search/*: explicit fields only, UTC instants with the hospital zone named."""

from datetime import datetime
from uuid import UUID

from scheduling.use_cases.search_types import (
    AnyResult,
    HospitalResult,
    Opening,
    ProviderResult,
    SearchPage,
    SpecialtyResult,
)
from scheduling.views.booking_schemas import format_instant


def search_body(page: SearchPage[AnyResult]) -> dict[str, object]:
    return {
        "results": [_result_body(result) for result in page.results],
        "total": page.total,
        "page": page.page,
        "page_count": page.page_count,
        "page_size": page.page_size,
    }


def _result_body(result: ProviderResult | HospitalResult | SpecialtyResult) -> dict[str, object]:
    if isinstance(result, ProviderResult):
        return _provider_body(result)
    if isinstance(result, HospitalResult):
        return _hospital_body(result)
    return _specialty_body(result)


def _slot_body(
    starts_at: datetime, clinician_id: UUID, appointment_type_id: UUID, time_zone: str
) -> dict[str, object]:
    return {
        "starts_at": format_instant(starts_at),
        "clinician_id": str(clinician_id),
        "appointment_type_id": str(appointment_type_id),
        "time_zone": time_zone,
    }


def _opening_body(opening: Opening | None) -> dict[str, object] | None:
    if opening is None:
        return None
    return _slot_body(
        opening.starts_at, opening.clinician_id, opening.appointment_type_id, opening.time_zone
    )


def _provider_body(result: ProviderResult) -> dict[str, object]:
    return {
        "id": str(result.id),
        "full_name": result.full_name,
        "title": result.title,
        "specialty": {"id": str(result.specialty_id), "name": result.specialty_name},
        "hospital": {
            "id": str(result.hospital_id),
            "name": result.hospital_name,
            "city": result.city,
            "time_zone": result.time_zone,
        },
        "department": {"id": str(result.department_id), "name": result.department_name},
        "appointment_type": {
            "id": str(result.appointment_type_id),
            "name": result.appointment_type_name,
            "duration_minutes": result.appointment_type_minutes,
        },
        "next_availabilities": [
            _slot_body(start, result.id, result.appointment_type_id, result.time_zone)
            for start in result.next_starts
        ],
        "has_availability": result.has_availability,
    }


def _hospital_body(result: HospitalResult) -> dict[str, object]:
    return {
        "id": str(result.id),
        "name": result.name,
        "street_address": result.street_address,
        "postal_code": result.postal_code,
        "city": result.city,
        "country": result.country,
        "time_zone": result.time_zone,
        "specialties": result.specialty_names,
        "bookable_provider_count": result.bookable_provider_count,
        "earliest_availability": _opening_body(result.earliest),
        "providers_with_availability_count": result.providers_with_availability_count,
        "has_availability": result.has_availability,
    }


def _specialty_body(result: SpecialtyResult) -> dict[str, object]:
    return {
        "id": str(result.id),
        "name": result.name,
        "provider_count": result.provider_count,
        "hospital_count": result.hospital_count,
        "earliest_availability": _opening_body(result.earliest),
        "has_availability": result.has_availability,
    }
