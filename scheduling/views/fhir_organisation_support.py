"""Request bodies the organisation write tests send."""

from scheduling.domain.fhir_common import LOCATION_TYPE_SYSTEM, ORGANIZATION_TYPE_SYSTEM
from scheduling.models import Department, Hospital
from scheduling.views.fhir_test_support import BASE, extension

CODE_SYSTEM = f"{BASE}/identifier/code"


def identifier(code: str) -> list[dict[str, str]]:
    return [{"system": CODE_SYSTEM, "value": code}]


def site_body(code: str = "saint-anne") -> dict[str, object]:
    return {
        "resourceType": "Location",
        "name": "Saint Anne Hospital",
        "identifier": identifier(code),
        "status": "active",
        "physicalType": {"coding": [{"system": LOCATION_TYPE_SYSTEM, "code": "si"}]},
        "address": {
            "line": ["2 Anne Street"],
            "city": "Hamburg",
            "postalCode": "20095",
            "country": "DE",
        },
        "telecom": [{"system": "phone", "value": "+49 40 5550"}],
        "extension": [extension("hospital-time-zone", valueCode="Europe/Berlin")],
    }


def department_body(hospital: Hospital, code: str = "cardio") -> dict[str, object]:
    return {
        "resourceType": "Organization",
        "name": "Cardiology",
        "identifier": identifier(code),
        "active": True,
        "type": [{"coding": [{"system": ORGANIZATION_TYPE_SYSTEM, "code": "dept"}]}],
        "partOf": {"reference": f"Organization/{hospital.pk}"},
    }


def service_body(department: Department, code: str = "intake") -> dict[str, object]:
    return {
        "resourceType": "HealthcareService",
        "name": "Intake visit",
        "identifier": identifier(code),
        "active": True,
        "providedBy": {"reference": f"Organization/{department.pk}"},
        "extension": [
            extension("service-duration-minutes", valueInteger=45),
            extension("service-buffer-minutes", valueInteger=5),
            extension("service-colour", valueString="#112233"),
            extension("service-needs-room", valueBoolean=False),
            extension("service-bookable-online", valueBoolean=True),
        ],
    }


def room_body(department: Department, code: str = "room-nine") -> dict[str, object]:
    return {
        "resourceType": "Location",
        "name": "Room nine",
        "identifier": identifier(code),
        "status": "active",
        "physicalType": {"coding": [{"system": LOCATION_TYPE_SYSTEM, "code": "ro"}]},
        "managingOrganization": {"reference": f"Organization/{department.pk}"},
        "extension": [
            extension("room-floor", valueString="2"),
            extension("room-capacity", valueInteger=3),
        ],
    }
