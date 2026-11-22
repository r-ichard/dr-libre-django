"""Task 22, spec 15.4 and 15.5: the one declaration the routes, the search parser and the
CapabilityStatement all read, so none of them can name what another does not."""

from dataclasses import dataclass
from enum import StrEnum

READ_ONLY = ("read", "search-type")
COMMON_PARAMETERS = ("_count", "_offset", "_sort", "_format", "_include")
SORTABLE_PARAMETERS = ("name", "address-city", "active")


class ParameterKind(StrEnum):
    TEXT = "text"
    FLAG = "flag"
    REFERENCE = "reference"
    CODE = "code"
    NEAR = "near"
    DATE = "date"


# FHIR search parameter type of each kind, for the CapabilityStatement.
FHIR_TYPE_OF_KIND = {
    ParameterKind.TEXT: "string",
    ParameterKind.FLAG: "token",
    ParameterKind.REFERENCE: "reference",
    ParameterKind.CODE: "token",
    ParameterKind.NEAR: "special",
    ParameterKind.DATE: "date",
}


@dataclass(frozen=True)
class SearchParameter:
    name: str
    kind: ParameterKind
    maximum_repeats: int = 1
    required: bool = False


@dataclass(frozen=True)
class ResourceDeclaration:
    type: str
    parameters: tuple[SearchParameter, ...]
    includes: tuple[str, ...] = ()
    single_id: str = ""
    interactions: tuple[str, ...] = READ_ONLY

    @property
    def sortable(self) -> tuple[str, ...]:
        names = {parameter.name for parameter in self.parameters}
        return tuple(name for name in SORTABLE_PARAMETERS if name in names)

    def parameter(self, name: str) -> SearchParameter | None:
        return next((item for item in self.parameters if item.name == name), None)


def _parameters(*pairs: tuple[str, ParameterKind]) -> tuple[SearchParameter, ...]:
    return tuple(SearchParameter(name, kind) for name, kind in pairs)


_TEXT = ParameterKind.TEXT
_FLAG = ParameterKind.FLAG
_REFERENCE = ParameterKind.REFERENCE
_CODE = ParameterKind.CODE
_DATE = ParameterKind.DATE

FHIR_RESOURCES = (
    ResourceDeclaration(
        "Organization",
        _parameters(
            ("name", _TEXT),
            ("type", _CODE),
            ("partof", _REFERENCE),
            ("address-city", _TEXT),
            ("active", _FLAG),
        ),
        interactions=(*READ_ONLY, "create", "update", "delete"),
    ),
    ResourceDeclaration(
        "Location",
        _parameters(
            ("name", _TEXT),
            ("address-city", _TEXT),
            ("organization", _REFERENCE),
            ("partof", _REFERENCE),
            ("type", _CODE),
            ("near", ParameterKind.NEAR),
        ),
        interactions=(*READ_ONLY, "create", "update", "delete"),
    ),
    ResourceDeclaration(
        "HealthcareService",
        _parameters(
            ("name", _TEXT),
            ("organization", _REFERENCE),
            ("specialty", _CODE),
            ("active", _FLAG),
        ),
        interactions=(*READ_ONLY, "create", "update", "delete"),
    ),
    ResourceDeclaration(
        "CodeSystem", (), single_id="specialty", interactions=(*READ_ONLY, "update")
    ),
    ResourceDeclaration("ValueSet", (), single_id="specialty"),
    ResourceDeclaration("Practitioner", _parameters(("name", _TEXT), ("active", _FLAG))),
    ResourceDeclaration(
        "PractitionerRole",
        _parameters(
            ("practitioner", _REFERENCE),
            ("organization", _REFERENCE),
            ("specialty", _CODE),
            ("location", _REFERENCE),
            ("service", _REFERENCE),
            ("active", _FLAG),
        ),
        includes=("PractitionerRole:practitioner", "PractitionerRole:organization"),
    ),
    ResourceDeclaration(
        "Schedule",
        _parameters(("actor", _REFERENCE), ("date", _DATE), ("active", _FLAG)),
        interactions=(*READ_ONLY, "create", "update", "delete"),
    ),
    ResourceDeclaration(
        "Slot",
        (
            SearchParameter("schedule", ParameterKind.REFERENCE),
            SearchParameter("schedule.actor", ParameterKind.REFERENCE),
            SearchParameter("service-type", ParameterKind.CODE, required=True),
            SearchParameter("start", ParameterKind.DATE, maximum_repeats=2, required=True),
            SearchParameter("status", ParameterKind.CODE, maximum_repeats=4),
        ),
        includes=("Slot:schedule",),
        interactions=READ_ONLY,
    ),
    ResourceDeclaration(
        "Patient",
        _parameters(("name", _TEXT), ("email", _TEXT), ("phone", _TEXT), ("birthdate", _DATE)),
        interactions=(*READ_ONLY, "update"),
    ),
    ResourceDeclaration(
        "Appointment",
        (
            *_parameters(
                ("patient", _REFERENCE),
                ("practitioner", _REFERENCE),
                ("location", _REFERENCE),
                ("status", _CODE),
                ("service-type", _CODE),
            ),
            SearchParameter("date", ParameterKind.DATE, maximum_repeats=2),
        ),
        includes=("Appointment:patient", "Appointment:practitioner", "Appointment:location"),
        interactions=(*READ_ONLY, "create", "update"),
    ),
    ResourceDeclaration("AppointmentResponse", (), interactions=(*READ_ONLY, "create")),
    ResourceDeclaration(
        "Communication",
        (
            *_parameters(("recipient", _REFERENCE), ("category", _CODE)),
            SearchParameter("sent", ParameterKind.DATE, maximum_repeats=2),
        ),
        interactions=(*READ_ONLY, "update"),
    ),
    ResourceDeclaration(
        "AuditEvent",
        (
            *_parameters(
                ("agent", _REFERENCE),
                ("entity", _CODE),
                ("entity-type", _CODE),
                ("action", _CODE),
            ),
            SearchParameter("date", ParameterKind.DATE, maximum_repeats=2),
        ),
    ),
)


def declaration_for(type_name: str) -> ResourceDeclaration | None:
    return next((item for item in FHIR_RESOURCES if item.type == type_name), None)
