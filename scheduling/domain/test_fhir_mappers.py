"""Section 15.2: the mapping table, one resource at a time, stated as exact bodies."""

from datetime import UTC, datetime, time
from uuid import UUID

from scheduling.domain.fhir_location import RoomSource, SiteSource, room_location, site_location
from scheduling.domain.fhir_organization import (
    OrganizationSource,
    department_organization,
    hospital_organization,
)
from scheduling.domain.fhir_practitioner import (
    PractitionerContact,
    PractitionerSource,
    practitioner,
)
from scheduling.domain.fhir_practitioner_role import (
    RoleSource,
    RuleHours,
    available_time,
    practitioner_role,
)
from scheduling.domain.fhir_service import ServiceSource, healthcare_service
from scheduling.domain.fhir_specialty import (
    SpecialtyList,
    specialty_code_system,
    specialty_value_set,
)

FIRST = UUID(int=1)
SECOND = UUID(int=2)
THIRD = UUID(int=3)
MOMENT = datetime(2026, 3, 4, 5, 6, 7, 891000, tzinfo=UTC)
META = {"versionId": "7", "lastUpdated": "2026-03-04T05:06:07.891Z"}
BASE = "https://drlibre.example/fhir"
SPECIALTY = f"{BASE}/CodeSystem/specialty"


def _extension(name: str, key: str, value: object) -> dict[str, object]:
    return {"url": f"{BASE}/StructureDefinition/{name}", key: value}


def returns_prov_organization_without_part_of_when_hospital_mapped() -> None:
    source = OrganizationSource(FIRST, "Riverside", 7, MOMENT, True, None)

    assert hospital_organization(source) == {
        "resourceType": "Organization",
        "id": str(FIRST),
        "meta": META,
        "active": True,
        "type": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                        "code": "prov",
                        "display": "Healthcare Provider",
                    }
                ]
            }
        ],
        "name": "Riverside",
    }


def returns_dept_organization_part_of_hospital_when_department_mapped() -> None:
    source = OrganizationSource(SECOND, "Cardiology", 7, MOMENT, False, FIRST)

    resource = department_organization(source)

    assert resource["partOf"] == {"reference": f"Organization/{FIRST}"}
    assert resource["active"] is False
    assert resource["type"] == [
        {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                    "code": "dept",
                    "display": "Hospital Department",
                }
            ]
        }
    ]


def returns_no_part_of_when_department_has_no_hospital() -> None:
    source = OrganizationSource(SECOND, "Cardiology", 7, MOMENT, True, None)

    assert "partOf" not in department_organization(source)


def _site(latitude: float | None, longitude: float | None, active: bool = True) -> SiteSource:
    return SiteSource(
        FIRST, "Riverside", 7, MOMENT, active, "1 Main St", "10115", "Berlin", "DE",
        "+4930123", "Europe/Berlin", latitude, longitude,
    )  # fmt: skip


def returns_site_with_address_phone_position_and_time_zone_when_hospital_mapped() -> None:
    assert site_location(_site(52.5, 13.4)) == {
        "resourceType": "Location",
        "id": str(FIRST),
        "meta": META,
        "extension": [_extension("hospital-time-zone", "valueCode", "Europe/Berlin")],
        "status": "active",
        "name": "Riverside",
        "telecom": [{"system": "phone", "value": "+4930123"}],
        "address": {
            "line": ["1 Main St"],
            "city": "Berlin",
            "postalCode": "10115",
            "country": "DE",
        },
        "physicalType": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/location-physical-type",
                    "code": "si",
                    "display": "Site",
                }
            ]
        },
        "managingOrganization": {"reference": f"Organization/{FIRST}"},
        "position": {"longitude": 13.4, "latitude": 52.5},
    }


def returns_no_position_when_either_coordinate_is_missing() -> None:
    assert "position" not in site_location(_site(None, 13.4))
    assert "position" not in site_location(_site(52.5, None))
    assert "position" in site_location(_site(0.0, 0.0))


def returns_inactive_status_when_site_is_inactive() -> None:
    assert site_location(_site(None, None, active=False))["status"] == "inactive"


def returns_room_with_floor_capacity_equipment_and_parents_when_room_mapped() -> None:
    source = RoomSource(THIRD, "Room 4", 7, MOMENT, False, FIRST, SECOND, "2", 3, ("ECG", "Bed"))

    assert room_location(source) == {
        "resourceType": "Location",
        "id": str(THIRD),
        "meta": META,
        "extension": [
            _extension("room-floor", "valueString", "2"),
            _extension("room-capacity", "valueInteger", 3),
            _extension("room-equipment", "valueString", "ECG"),
            _extension("room-equipment", "valueString", "Bed"),
        ],
        "status": "inactive",
        "name": "Room 4",
        "physicalType": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/location-physical-type",
                    "code": "ro",
                    "display": "Room",
                }
            ]
        },
        "managingOrganization": {"reference": f"Organization/{SECOND}"},
        "partOf": {"reference": f"Location/{FIRST}"},
    }


def returns_active_status_when_room_is_active() -> None:
    source = RoomSource(THIRD, "Room 4", 7, MOMENT, True, FIRST, SECOND, "2", 3, ())

    assert room_location(source)["status"] == "active"


def returns_service_with_extensions_and_specialties_when_appointment_type_mapped() -> None:
    source = ServiceSource(
        FIRST, "Check-up", 7, MOMENT, True, SECOND, 30, 5, "#112233", True, False,
        (("cardio", "Cardiology"),),
    )  # fmt: skip

    assert healthcare_service(source) == {
        "resourceType": "HealthcareService",
        "id": str(FIRST),
        "meta": META,
        "extension": [
            _extension("service-duration-minutes", "valueInteger", 30),
            _extension("service-buffer-minutes", "valueInteger", 5),
            _extension("service-colour", "valueString", "#112233"),
            _extension("service-needs-room", "valueBoolean", True),
            _extension("service-bookable-online", "valueBoolean", False),
        ],
        "active": True,
        "providedBy": {"reference": f"Organization/{SECOND}"},
        "type": [{"text": "Check-up"}],
        "specialty": [
            {"coding": [{"system": SPECIALTY, "code": "cardio", "display": "Cardiology"}]}
        ],
        "name": "Check-up",
    }


def returns_code_system_and_value_set_of_all_specialties_when_list_mapped() -> None:
    source = SpecialtyList(7, MOMENT, (("cardio", "Cardiology"), ("derm", "Dermatology")))

    assert specialty_code_system(source) == {
        "resourceType": "CodeSystem",
        "id": "specialty",
        "meta": META,
        "url": SPECIALTY,
        "name": "DrLibreSpecialty",
        "status": "active",
        "content": "complete",
        "caseSensitive": False,
        "property": [
            {
                "code": "inactive",
                "uri": "http://hl7.org/fhir/concept-properties#inactive",
                "type": "boolean",
            }
        ],
        "count": 2,
        "concept": [
            {"code": "cardio", "display": "Cardiology"},
            {"code": "derm", "display": "Dermatology"},
        ],
    }
    assert specialty_value_set(source) == {
        "resourceType": "ValueSet",
        "id": "specialty",
        "meta": META,
        "url": f"{BASE}/ValueSet/specialty",
        "name": "DrLibreSpecialty",
        "status": "active",
        "compose": {"include": [{"system": SPECIALTY}]},
    }


def returns_name_and_title_only_when_practitioner_mapped() -> None:
    source = PractitionerSource(FIRST, "Dr Ada Hart", "Cardiologist", 7, MOMENT, False)

    assert practitioner(source) == {
        "resourceType": "Practitioner",
        "id": str(FIRST),
        "meta": META,
        "active": False,
        "name": [{"text": "Dr Ada Hart"}],
        "qualification": [{"code": {"text": "Cardiologist"}}],
    }


def _role(bio: str = "", room: UUID | None = None, rules: tuple[RuleHours, ...] = ()) -> RoleSource:
    return RoleSource(
        FIRST, SECOND, THIRD, "cardio", "Cardiology", room, bio, 4, 7, MOMENT, True,
        (SECOND, FIRST), rules,
    )  # fmt: skip


def returns_role_with_references_weight_and_services_when_profile_mapped() -> None:
    rules = (RuleHours(1, time(9), time(17)),)

    assert practitioner_role(_role("Hello", FIRST, rules)) == {
        "resourceType": "PractitionerRole",
        "id": str(FIRST),
        "meta": META,
        "extension": [
            _extension("role-round-robin-weight", "valueInteger", 4),
            _extension("role-bio", "valueString", "Hello"),
        ],
        "active": True,
        "practitioner": {"reference": f"Practitioner/{SECOND}"},
        "organization": {"reference": f"Organization/{THIRD}"},
        "specialty": [
            {"coding": [{"system": SPECIALTY, "code": "cardio", "display": "Cardiology"}]}
        ],
        "healthcareService": [
            {"reference": f"HealthcareService/{SECOND}"},
            {"reference": f"HealthcareService/{FIRST}"},
        ],
        "availableTime": [
            {
                "daysOfWeek": ["mon"],
                "availableStartTime": "09:00:00",
                "availableEndTime": "17:00:00",
            }
        ],
        "location": [{"reference": f"Location/{FIRST}"}],
    }


def returns_no_bio_extension_and_no_location_when_both_are_empty() -> None:
    resource = practitioner_role(_role())

    assert len(resource["extension"]) == 1  # type: ignore[arg-type]
    assert "location" not in resource
    assert resource["availableTime"] == []


def returns_one_entry_per_hours_with_sorted_weekdays_when_rules_share_hours() -> None:
    morning = (time(8), time(12))
    rules = (
        RuleHours(5, *morning),
        RuleHours(0, *morning),
        RuleHours(3, *morning),
        RuleHours(3, *morning),
        RuleHours(2, time(13), time(15, 30, 5)),
    )

    assert available_time(rules) == [
        {
            "daysOfWeek": ["sun", "wed", "fri"],
            "availableStartTime": "08:00:00",
            "availableEndTime": "12:00:00",
        },
        {
            "daysOfWeek": ["tue"],
            "availableStartTime": "13:00:00",
            "availableEndTime": "15:30:05",
        },
    ]


def returns_every_weekday_name_when_weekday_is_numbered_from_sunday() -> None:
    names = [
        available_time((RuleHours(day, time(1), time(2)),))[0]["daysOfWeek"][0]  # type: ignore[index]
        for day in range(7)
    ]

    assert names == ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]


def returns_telecom_when_practitioner_has_contact() -> None:
    contact = PractitionerContact("ada@example.org", "+49 30 1")
    source = PractitionerSource(FIRST, "Dr Ada Hart", "Cardiologist", 7, MOMENT, True, contact)

    assert practitioner(source)["telecom"] == [
        {"system": "email", "value": "ada@example.org"},
        {"system": "phone", "value": "+49 30 1"},
    ]


def returns_email_only_when_practitioner_has_no_phone() -> None:
    contact = PractitionerContact("ada@example.org", "")
    source = PractitionerSource(FIRST, "Dr Ada Hart", "Cardiologist", 7, MOMENT, True, contact)

    assert practitioner(source)["telecom"] == [{"system": "email", "value": "ada@example.org"}]


def returns_inactive_property_only_on_listed_inactive_codes_when_code_system_mapped() -> None:
    source = SpecialtyList(
        7,
        MOMENT,
        (("cardio", "Cardiology"), ("derm", "Dermatology")),
        frozenset({"derm"}),
    )

    concepts = specialty_code_system(source)["concept"]

    assert concepts == [
        {"code": "cardio", "display": "Cardiology"},
        {
            "code": "derm",
            "display": "Dermatology",
            "property": [{"code": "inactive", "valueBoolean": True}],
        },
    ]
