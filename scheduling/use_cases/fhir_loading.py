"""Task 22, spec 15.2: rows to FHIR resources, a fixed number of queries for a whole page.
Explicit field lists only, so a column added to a model never reaches a body by default."""

from datetime import UTC, datetime
from uuid import UUID

from django.db import connection

from scheduling.domain.fhir_common import Resource
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
from scheduling.domain.fhir_practitioner_role import RoleSource, RuleHours, practitioner_role
from scheduling.domain.fhir_service import ServiceSource, healthcare_service
from scheduling.domain.fhir_specialty import (
    SpecialtyList,
    specialty_code_system,
    specialty_value_set,
)
from scheduling.models import (
    AppointmentType,
    AvailabilityRule,
    ClinicianProfile,
    Department,
    Hospital,
    Room,
    Specialty,
)
from scheduling.use_cases.search_catalog import bookable_types

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def hospital_organizations(ids: list[UUID]) -> list[Resource]:
    rows = Hospital.objects.filter(pk__in=ids).values_list(
        "id", "name", "version", "updated_at", "is_active"
    )
    return [hospital_organization(OrganizationSource(*row, None)) for row in rows]


def department_organizations(ids: list[UUID]) -> list[Resource]:
    rows = Department.objects.filter(pk__in=ids).values_list(
        "id", "name", "version", "updated_at", "hospital_id"
    )
    return [department_organization(OrganizationSource(*row[:4], True, row[4])) for row in rows]


def site_locations(ids: list[UUID]) -> list[Resource]:
    rows = Hospital.objects.filter(pk__in=ids).values_list(
        "id",
        "name",
        "version",
        "updated_at",
        "is_active",
        "street_address",
        "postal_code",
        "city",
        "country",
        "phone",
        "time_zone",
        "latitude",
        "longitude",
    )
    return [site_location(SiteSource(*row)) for row in rows]


def room_locations(ids: list[UUID]) -> list[Resource]:
    rows = Room.objects.filter(pk__in=ids).values_list(
        "id",
        "name",
        "version",
        "updated_at",
        "is_active",
        "department__hospital_id",
        "department_id",
        "floor",
        "capacity",
        "equipment",
    )
    return [room_location(RoomSource(*row[:9], tuple(row[9]))) for row in rows]


def healthcare_services(ids: list[UUID]) -> list[Resource]:
    rows = list(
        AppointmentType.objects.filter(pk__in=ids).values_list(
            "id",
            "name",
            "version",
            "updated_at",
            "is_active",
            "department_id",
            "duration_minutes",
            "buffer_minutes",
            "colour",
            "needs_room",
            "is_bookable_online",
        )
    )
    specialties: dict[UUID, set[tuple[str, str]]] = {}
    pairs = (
        ClinicianProfile.objects.filter(department_id__in={row[5] for row in rows})
        .values_list("department_id", "specialty__code", "specialty__name")
        .distinct()
    )
    for department_id, code, name in pairs:
        specialties.setdefault(department_id, set()).add((code, name))
    return [
        healthcare_service(ServiceSource(*row, tuple(sorted(specialties.get(row[5], ())))))
        for row in rows
    ]


def specialty_list() -> SpecialtyList:
    rows = list(Specialty.objects.filter(is_active=True).order_by("code"))
    with connection.cursor() as cursor:
        cursor.execute("SELECT last_value FROM scheduling_specialty_revision")
        revision = cursor.fetchone()
    version = int(revision[0]) if revision else 1
    updated = max((row.updated_at for row in rows), default=EPOCH)
    return SpecialtyList(version, updated, tuple((row.code, row.name) for row in rows))


def specialty_code_system_resource() -> Resource:
    return specialty_code_system(specialty_list())


def specialty_value_set_resource() -> Resource:
    return specialty_value_set(specialty_list())


def practitioners(user_ids: list[UUID]) -> list[Resource]:
    rows = ClinicianProfile.objects.filter(user_id__in=user_ids).values_list(
        "user_id",
        "user__full_name",
        "title",
        "user__version",
        "user__updated_at",
        "user__is_active",
    )
    return [practitioner(PractitionerSource(*row)) for row in rows]


def practitioners_with_contact(user_ids: list[UUID]) -> list[Resource]:
    """For a staff token only (15.4): the same body plus email and phone."""
    rows = ClinicianProfile.objects.filter(user_id__in=user_ids).values_list(
        "user_id",
        "user__full_name",
        "title",
        "user__version",
        "user__updated_at",
        "user__is_active",
        "user__email",
        "user__phone",
    )
    return [
        practitioner(PractitionerSource(*row[:6], PractitionerContact(*row[6:]))) for row in rows
    ]


def practitioner_roles(profile_ids: list[UUID]) -> list[Resource]:
    profiles = list(
        ClinicianProfile.objects.filter(pk__in=profile_ids).values_list(
            "id",
            "user_id",
            "department_id",
            "specialty__code",
            "specialty__name",
            "default_room_id",
            "bio",
            "round_robin_weight",
            "version",
            "updated_at",
            "user__is_active",
        )
    )
    rules: dict[UUID, list[RuleHours]] = {}
    for clinician_id, weekday, start, end in AvailabilityRule.objects.filter(
        clinician_id__in=profile_ids
    ).values_list("clinician_id", "weekday", "start_time", "end_time"):
        rules.setdefault(clinician_id, []).append(RuleHours(weekday, start, end))
    services: dict[UUID, list[UUID]] = {}
    for department_id, type_id in (
        bookable_types()
        .filter(department_id__in={row[2] for row in profiles})
        .order_by("name", "id")
        .values_list("department_id", "id")
    ):
        services.setdefault(department_id, []).append(type_id)
    return [
        practitioner_role(
            RoleSource(
                *row,
                service_ids=tuple(services.get(row[2], ())),
                rules=tuple(rules.get(row[0], ())),
            )
        )
        for row in profiles
    ]
