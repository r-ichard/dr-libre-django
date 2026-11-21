"""Section 14 GET /providers/{id}, /hospitals/{id}, /specialties/{id}: explicit fields only."""

from scheduling.use_cases.public_details import HospitalDetail, Named, ProviderDetail
from scheduling.views.search_schemas import provider_body


def provider_detail_body(detail: ProviderDetail) -> dict[str, object]:
    result = detail.provider
    return {
        "id": str(result.id),
        "full_name": result.full_name,
        "title": result.title,
        "bio": detail.bio,
        "specialty": {"id": str(result.specialty_id), "name": result.specialty_name},
        "hospital": {
            "id": str(result.hospital_id),
            "name": result.hospital_name,
            "city": result.city,
            "time_zone": result.time_zone,
        },
        "department": {"id": str(result.department_id), "name": result.department_name},
        "appointment_types": [
            {"id": str(item.id), "name": item.name, "duration_minutes": item.duration_minutes}
            for item in detail.appointment_types
        ],
    }


def hospital_detail_body(detail: HospitalDetail) -> dict[str, object]:
    return {
        "id": str(detail.id),
        "name": detail.name,
        "description": detail.description,
        "street_address": detail.street_address,
        "postal_code": detail.postal_code,
        "city": detail.city,
        "country": detail.country,
        "phone": detail.phone,
        "time_zone": detail.time_zone,
        "departments": [_named_body(item) for item in detail.departments],
        "specialties": [_named_body(item) for item in detail.specialties],
        "providers": [provider_body(item) for item in detail.providers],
    }


def _named_body(item: Named) -> dict[str, str]:
    return {"id": str(item.id), "name": item.name}
