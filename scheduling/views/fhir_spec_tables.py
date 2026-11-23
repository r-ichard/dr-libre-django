"""Spec 15.2, 15.4 and 15.5 of drlibre-specs.md as data, a copy independent of
`scheduling/domain/fhir_declaration.py`. A departure from the letter is a `Difference`
that names the ADR giving the reason."""

from collections.abc import Mapping
from dataclasses import dataclass

PUBLIC = "public"
PATIENT = "patient"
CLINICIAN = "clinician"
ADMIN = "admin"
ROLES = (PUBLIC, PATIENT, CLINICIAN, ADMIN)
EVERYONE = ROLES
SIGNED_IN = (PATIENT, CLINICIAN, ADMIN)
INTERACTIONS = ("read", "search-type", "create", "update", "delete")


@dataclass(frozen=True)
class Difference:
    """`interaction` is dropped (`kind` "missing"), added ("extra") or, for `role`, answered 200
    with an empty result instead of a refusal ("scoped"). `quote` is a phrase the ADR must hold."""

    interaction: str
    kind: str
    adr: str
    reason: str
    quote: str
    role: str = ""


@dataclass(frozen=True)
class Addition:
    """A search parameter served that the tables of section 15 do not name: the ADR that adds it
    and a phrase it must hold."""

    resource: str
    parameter: str
    adr: str
    quote: str


ADR_ADDITIONS = (Addition("AuditEvent", "type", "0009", "`AuditEvent?type=<action>`"),)


@dataclass(frozen=True)
class SpecResource:
    type: str
    readers: tuple[str, ...]
    writers: Mapping[str, tuple[str, ...]]
    parameters: tuple[str, ...] = ()
    includes: tuple[str, ...] = ()
    differences: tuple[Difference, ...] = ()


ADMIN_ONLY = (ADMIN,)
ADMIN_WRITES = {"create": ADMIN_ONLY, "update": ADMIN_ONLY, "delete": ADMIN_ONLY}

SPEC_RESOURCES = (
    SpecResource(
        "Organization",
        EVERYONE,
        ADMIN_WRITES,
        ("name", "type", "partof", "address-city", "active"),
    ),
    SpecResource(
        "Location",
        EVERYONE,
        ADMIN_WRITES,
        ("name", "address-city", "organization", "partof", "type", "near"),
    ),
    SpecResource(
        "HealthcareService",
        EVERYONE,
        ADMIN_WRITES,
        ("name", "organization", "specialty", "active"),
    ),
    SpecResource(
        "CodeSystem",
        EVERYONE,
        ADMIN_WRITES,
        differences=(
            Difference("create", "missing", "0008", "one fixed id", "No `POST` (one fixed id)"),
            Difference("delete", "missing", "0008", "a PUT omits concepts", "no `DELETE`"),
        ),
    ),
    SpecResource(
        "ValueSet",
        EVERYONE,
        ADMIN_WRITES,
        differences=tuple(
            Difference(
                name,
                "missing",
                "0008",
                "read-only view of the list",
                "read-only view of the same list",
            )
            for name in ("create", "update", "delete")
        ),
    ),
    SpecResource(
        "Practitioner",
        EVERYONE,
        ADMIN_WRITES,
        ("name", "active"),
        differences=(
            Difference(
                "create",
                "missing",
                "0009",
                "a user is created in the console",
                "`POST /fhir/Practitioner` is not offered",
            ),
        ),
    ),
    SpecResource(
        "PractitionerRole",
        EVERYONE,
        {"create": ADMIN_ONLY, "update": (ADMIN, CLINICIAN), "delete": ADMIN_ONLY},
        ("practitioner", "organization", "specialty", "location", "service", "active"),
        ("PractitionerRole:practitioner", "PractitionerRole:organization"),
    ),
    SpecResource(
        "Schedule",
        EVERYONE,
        {"create": (CLINICIAN,), "update": (CLINICIAN,), "delete": (CLINICIAN,)},
        ("actor", "date", "active"),
    ),
    SpecResource(
        "Slot",
        EVERYONE,
        {},
        ("schedule", "schedule.actor", "service-type", "start", "status"),
        ("Slot:schedule",),
    ),
    SpecResource(
        "Patient",
        SIGNED_IN,
        {"update": (PATIENT, ADMIN)},
        ("name", "email", "phone", "birthdate"),
    ),
    SpecResource(
        "Appointment",
        SIGNED_IN,
        {"create": SIGNED_IN, "update": SIGNED_IN},
        ("patient", "practitioner", "location", "status", "date", "service-type"),
        ("Appointment:patient", "Appointment:practitioner", "Appointment:location"),
    ),
    SpecResource(
        "AppointmentResponse",
        (PATIENT, ADMIN),
        {"create": (PATIENT, ADMIN)},
        differences=(
            Difference(
                "search-type",
                "scoped",
                "0007",
                "a clinician searches and finds none, as for a slot status",
                "clinician searching `AppointmentResponse` gets an empty search",
                CLINICIAN,
            ),
        ),
    ),
    SpecResource(
        "Communication",
        SIGNED_IN,
        {"update": SIGNED_IN},
        ("recipient", "category", "sent"),
    ),
    SpecResource(
        "AuditEvent",
        ADMIN_ONLY,
        {},
        ("agent", "entity", "entity-type", "action", "date"),
    ),
)
