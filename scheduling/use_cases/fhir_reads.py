"""Task 22, spec 15.4: what a caller without a token reads and searches through /fhir.
A part is the rows of one table answering for a resource type (a hospital is an Organization
and a Location). Visibility reuses `search_catalog`, the application API rule."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from django.db.models import Model, QuerySet

from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_declaration import declaration_for
from scheduling.domain.fhir_near import is_within, parse_near
from scheduling.domain.fhir_search import SearchQuery
from scheduling.models import AppointmentType, ClinicianProfile, Department, Hospital, Room
from scheduling.use_cases import fhir_loading as loading
from scheduling.use_cases.search_catalog import bookable_types, listable_profiles


class Viewer(StrEnum):
    """PUBLIC: no token, or a patient's. STAFF: a clinician's or an admin's token (15.4)."""

    PUBLIC = "public"
    STAFF = "staff"


type Filter = Callable[[QuerySet[Model], str], QuerySet[Model]]


@dataclass(frozen=True)
class Part:
    visible: Callable[[], QuerySet[Model]]
    everything: Callable[[], QuerySet[Model]]
    id_column: str
    sort_columns: Mapping[str, str]
    filters: Mapping[str, Filter]
    build: Callable[[list[UUID]], list[Resource]]
    staff_build: Callable[[list[UUID]], list[Resource]] | None = None

    def rows(self, viewer: Viewer) -> QuerySet[Model]:
        return self.everything() if viewer is Viewer.STAFF else self.visible()

    def built(self, ids: list[UUID], viewer: Viewer) -> list[Resource]:
        use = self.staff_build if viewer is Viewer.STAFF and self.staff_build else self.build
        return use(ids)


@dataclass(frozen=True)
class SearchPage:
    total: int
    matches: list[Resource]
    included: list[Resource]


def _contains(column: str) -> Filter:
    return lambda rows, value: rows.filter(**{f"{column}__icontains": value})


def _equals(column: str) -> Filter:
    return lambda rows, value: rows.filter(**{column: value})


def _equals_ignoring_case(column: str) -> Filter:
    return lambda rows, value: rows.filter(**{f"{column}__iexact": value})


def _flag(column: str) -> Filter:
    return lambda rows, value: rows.filter(**{column: value == "true"})


def _only_when(wanted: str) -> Filter:
    return lambda rows, value: rows if value == wanted else rows.none()


def _near(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    point = parse_near(value)
    if point is None:
        return rows.none()
    nearby = [
        pk
        for pk, latitude, longitude in rows.filter(latitude__isnull=False).values_list(
            "pk", "latitude", "longitude"
        )
        if is_within(point, latitude, longitude)
    ]
    return rows.filter(pk__in=nearby)


def _listable() -> QuerySet[ClinicianProfile]:
    return listable_profiles(bookable_types().values_list("department_id", flat=True))


HOSPITAL = Part(
    visible=lambda: Hospital.objects.filter(is_active=True),
    everything=lambda: Hospital.objects.all(),
    id_column="pk",
    sort_columns={"name": "name", "address-city": "city", "active": "is_active"},
    filters={
        "name": _contains("name"),
        "address-city": _contains("city"),
        "active": _flag("is_active"),
        "type": _only_when("prov"),
    },
    build=loading.hospital_organizations,
)
DEPARTMENT = Part(
    visible=lambda: Department.objects.filter(hospital__is_active=True),
    everything=lambda: Department.objects.all(),
    id_column="pk",
    sort_columns={"name": "name"},
    filters={
        "name": _contains("name"),
        "active": _only_when("true"),
        "type": _only_when("dept"),
        "partof": _equals("hospital_id"),
    },
    build=loading.department_organizations,
)
SITE = Part(
    visible=HOSPITAL.visible,
    everything=HOSPITAL.everything,
    id_column="pk",
    sort_columns={"name": "name", "address-city": "city"},
    filters={
        "name": _contains("name"),
        "address-city": _contains("city"),
        "organization": _equals("pk"),
        "type": _only_when("si"),
        "near": _near,
    },
    build=loading.site_locations,
)
ROOM = Part(
    visible=lambda: Room.objects.filter(is_active=True, department__hospital__is_active=True),
    everything=lambda: Room.objects.all(),
    id_column="pk",
    sort_columns={"name": "name"},
    filters={
        "name": _contains("name"),
        "organization": _equals("department_id"),
        "partof": _equals("department__hospital_id"),
        "type": _only_when("ro"),
    },
    build=loading.room_locations,
)
SERVICE = Part(
    visible=lambda: bookable_types().filter(department__hospital__is_active=True),
    everything=lambda: AppointmentType.objects.all(),
    id_column="pk",
    sort_columns={"name": "name", "active": "is_active"},
    filters={
        "name": _contains("name"),
        "organization": _equals("department_id"),
        "specialty": _equals_ignoring_case("department__clinicianprofile__specialty__code"),
        "active": _flag("is_active"),
    },
    build=loading.healthcare_services,
)
PRACTITIONER = Part(
    visible=_listable,
    everything=lambda: ClinicianProfile.objects.all(),
    id_column="user_id",
    sort_columns={"name": "user__full_name", "active": "user__is_active"},
    filters={"name": _contains("user__full_name"), "active": _flag("user__is_active")},
    build=loading.practitioners,
    staff_build=loading.practitioners_with_contact,
)
ROLE = Part(
    visible=_listable,
    everything=lambda: ClinicianProfile.objects.all(),
    id_column="pk",
    sort_columns={"name": "user__full_name", "active": "user__is_active"},
    filters={
        "practitioner": _equals("user_id"),
        "organization": _equals("department_id"),
        "specialty": _equals_ignoring_case("specialty__code"),
        "location": _equals("default_room_id"),
        "service": _equals("department__appointmenttype__pk"),
        "active": _flag("user__is_active"),
    },
    build=loading.practitioner_roles,
)

PARTS: dict[str, tuple[Part, ...]] = {
    "Organization": (HOSPITAL, DEPARTMENT),
    "Location": (SITE, ROOM),
    "HealthcareService": (SERVICE,),
    "Practitioner": (PRACTITIONER,),
    "PractitionerRole": (ROLE,),
}
SINGLE_BUILDERS: dict[str, Callable[[], Resource]] = {
    "CodeSystem": loading.specialty_code_system_resource,
    "ValueSet": loading.specialty_value_set_resource,
}


def read_resource(resource_type: str, identifier: str, viewer: Viewer) -> Result[Resource]:
    declaration = declaration_for(resource_type)
    if declaration is None:
        return Failure.not_found()
    if declaration.single_id:
        if identifier != declaration.single_id:
            return Failure.not_found()
        return Success(SINGLE_BUILDERS[resource_type]())
    for part in PARTS[resource_type]:
        if part.rows(viewer).filter(**{part.id_column: identifier}).exists():
            return Success(part.built([UUID(identifier)], viewer)[0])
    return Failure.not_found()


def search_resource(resource_type: str, query: SearchQuery, viewer: Viewer) -> Result[SearchPage]:
    declaration = declaration_for(resource_type)
    if declaration is None:
        return Failure.not_found()
    if declaration.single_id:
        single = [SINGLE_BUILDERS[resource_type]()] if query.offset == 0 and query.count else []
        return Success(SearchPage(1, single, []))
    candidates = _candidates(PARTS[resource_type], query, viewer)
    page = candidates[query.offset : query.offset + query.count]
    matches = _build_page(PARTS[resource_type], page, viewer)
    return Success(SearchPage(len(candidates), matches, _included(query, page, viewer)))


@dataclass(frozen=True)
class Candidate:
    sort_key: str
    identifier: UUID
    part_index: int


def _candidates(parts: tuple[Part, ...], query: SearchQuery, viewer: Viewer) -> list[Candidate]:
    found: list[Candidate] = []
    for index, part in enumerate(parts):
        rows = part.rows(viewer)
        for name, value in query.filters:
            refine = part.filters.get(name)
            rows = refine(rows, value) if refine else rows.none()
        column = part.sort_columns.get(query.sort, "pk")
        found += [
            Candidate(str(key).lower(), identifier, index)
            for key, identifier in rows.values_list(column, part.id_column).distinct()
        ]
    return sorted(
        found, key=lambda item: (item.sort_key, item.identifier), reverse=query.descending
    )


def _build_page(parts: tuple[Part, ...], page: list[Candidate], viewer: Viewer) -> list[Resource]:
    built: dict[UUID, Resource] = {}
    for index, part in enumerate(parts):
        wanted = [item.identifier for item in page if item.part_index == index]
        if wanted:
            built.update({UUID(str(item["id"])): item for item in part.built(wanted, viewer)})
    return [built[item.identifier] for item in page]


def _included(query: SearchQuery, page: list[Candidate], viewer: Viewer) -> list[Resource]:
    if not query.include or not page:
        return []
    links = list(
        ClinicianProfile.objects.filter(pk__in=[item.identifier for item in page]).values_list(
            "user_id", "department_id"
        )
    )
    users = sorted({user for user, _ in links})
    departments = sorted({department for _, department in links})
    if query.include[0] == "PractitionerRole:practitioner":
        return (
            loading.practitioners_with_contact(users)
            if viewer is Viewer.STAFF
            else loading.practitioners(users)
        )
    return loading.department_organizations(departments)
