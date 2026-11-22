"""Task 22, spec 15.2: rows to FHIR resources, a fixed number of queries for a whole page.
Explicit field lists only, so a column added to a model never reaches a body by default."""

from datetime import UTC, datetime
from uuid import UUID

from django.db import connection
from django.db.models import QuerySet

from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_location import RoomSource, SiteSource, room_location, site_location
from scheduling.domain.fhir_organization import (
    OrganizationSource,
    department_organization,
    hospital_organization,
)
from scheduling.domain.fhir_patient import PatientSource, patient_resource
from scheduling.domain.fhir_practitioner import (
    PractitionerContact,
    PractitionerSource,
    practitioner,
)
from scheduling.domain.fhir_practitioner_role import RoleSource, RuleHours, practitioner_role
from scheduling.domain.fhir_schedule import ScheduleSource, schedule_resource
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
    User,
)
from scheduling.use_cases.search_catalog import bookable_types

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def hospital_organizations(ids: list[UUID]) -> list[Resource]:
    rows = Hospital.objects.filter(pk__in=ids).values_list(
        "id", "name", "version", "updated_at", "is_active", "code"
    )
    return [hospital_organization(OrganizationSource(*row[:5], None, row[5])) for row in rows]


def department_organizations(ids: list[UUID]) -> list[Resource]:
    rows = Department.objects.filter(pk__in=ids).values_list(
        "id", "name", "version", "updated_at", "hospital_id", "code"
    )
    return [
        department_organization(OrganizationSource(*row[:4], True, row[4], row[5])) for row in rows
    ]


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
        "code",
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
        "code",
    )
    return [room_location(RoomSource(*row[:9], tuple(row[9]), row[10])) for row in rows]


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
            "code",
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
        healthcare_service(
            ServiceSource(*row[:11], tuple(sorted(specialties.get(row[5], ()))), row[11])
        )
        for row in rows
    ]


def specialty_revision() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT last_value FROM scheduling_specialty_revision")
        revision = cursor.fetchone()
    return int(revision[0]) if revision else 1


def specialty_list(*, include_inactive: bool) -> SpecialtyList:
    """Staff read every specialty with the inactive ones flagged, so a client that reads the list
    and writes it back does not delete what is switched off; the public reads active ones."""
    rows = Specialty.objects.order_by("code")
    if not include_inactive:
        rows = rows.filter(is_active=True)
    listed = list(rows)
    updated = max((row.updated_at for row in listed), default=EPOCH)
    inactive = frozenset(row.code for row in listed if not row.is_active)
    concepts = tuple((row.code, row.name) for row in listed)
    return SpecialtyList(specialty_revision(), updated, concepts, inactive)


def specialty_code_system_resource(*, include_inactive: bool) -> Resource:
    return specialty_code_system(specialty_list(include_inactive=include_inactive))


def specialty_value_set_resource() -> Resource:
    return specialty_value_set(specialty_list(include_inactive=False))


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
    return _roles(profile_ids, bookable_types())


def practitioner_roles_with_all_services(profile_ids: list[UUID]) -> list[Resource]:
    """For a staff token: the services it can read itself, so the reference resolves."""
    return _roles(profile_ids, AppointmentType.objects.all())


def _roles(profile_ids: list[UUID], service_types: QuerySet[AppointmentType]) -> list[Resource]:
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
        service_types.filter(department_id__in={row[2] for row in profiles})
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


def schedules(rule_ids: list[UUID]) -> list[Resource]:
    rows = AvailabilityRule.objects.filter(pk__in=rule_ids).values_list(
        "id",
        "version",
        "updated_at",
        "clinician__user_id",
        "room_id",
        "valid_from",
        "valid_to",
        "weekday",
        "start_time",
        "end_time",
        "slot_step_minutes",
        "clinician__user__is_active",
    )
    return [schedule_resource(ScheduleSource(*row)) for row in rows]


def patients(user_ids: list[UUID]) -> list[Resource]:
    rows = User.objects.filter(pk__in=user_ids).values_list(
        "id", "full_name", "email", "phone", "date_of_birth", "is_active", "version", "updated_at"
    )
    return [patient_resource(PatientSource(*row)) for row in rows]
