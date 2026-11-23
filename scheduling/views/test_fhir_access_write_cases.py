"""The /fhir write cases the writes walk sends: one per walked write row, and one per hospital
variant. Each makes a fresh record per caller; a create's code is unique per caller."""

from collections.abc import Callable
from dataclasses import dataclass

from django.db.models import Model

from scheduling.models import AppointmentType, Department, Hospital, Room
from scheduling.models.builders import make
from scheduling.views.fhir_organisation_support import department_body, room_body, service_body
from scheduling.views.fhir_specialty_support import LIST_PATH, concept
from scheduling.views.test_fhir_access_world import World
from test_support.fhir_access_rows import Caller

WRITE_INTERACTIONS = ("create", "update", "delete")
RENAMED = "Renamed by the writes walk"

# The next run removes an entry as it adds the pair's case. An entry that gets a case without
# being removed here fails the coverage test.
NOT_WALKED_YET: frozenset[tuple[str, str]] = frozenset(
    {
        ("Practitioner", "update"),
        ("Practitioner", "delete"),
        ("PractitionerRole", "create"),
        ("PractitionerRole", "update"),
        ("PractitionerRole", "delete"),
        ("Schedule", "create"),
        ("Schedule", "update"),
        ("Schedule", "delete"),
        ("Patient", "update"),
        ("Appointment", "create"),
        ("Appointment", "update"),
        ("AppointmentResponse", "create"),
        ("Communication", "update"),
    }
)

# Gets the record as the admin read it before the write (None for a create); returns the body.
BodyBuilder = Callable[[World, Caller, object], dict[str, object]]


# The fields an accepted write must read back with the caller's values. The server adds fields of
# its own (meta, coding displays), so the walk compares the fields the case changes, not the body.
@dataclass(frozen=True)
class WriteCase:
    resource: str
    interaction: str
    record: str
    fresh: Callable[[World, Caller], str]
    body: BodyBuilder | None
    reads_back: tuple[str, ...] = ("name",)
    table: type[Model] | None = None


def _path(resource: str, record_id: object) -> str:
    return f"/fhir/{resource}/{record_id}"


def _collection(resource: str) -> Callable[[World, Caller], str]:
    return lambda _world, _caller: f"/fhir/{resource}"


def _fresh_department(world: World, _caller: Caller) -> str:
    department = make("Department", hospital=world.room.department.hospital)
    return _path("Organization", department.pk)


def _fresh_hospital(_world: World, _caller: Caller) -> str:
    return _path("Organization", make("Hospital").pk)


def _fresh_room(world: World, _caller: Caller) -> str:
    return _path("Location", make("Room", department=world.room.department).pk)


def _fresh_appointment_type(world: World, _caller: Caller) -> str:
    appointment_type = make("AppointmentType", department=world.room.department)
    return _path("HealthcareService", appointment_type.pk)


# The builders' names are fixed, so each create renames its body: a create that stores another
# name than the one sent then fails the read-back.
def _department_created(world: World, caller: Caller, _current: object) -> dict[str, object]:
    body = department_body(world.room.department.hospital, f"cardio-{caller}")
    return {**body, "name": f"Cardiology {caller}"}


def _room_created(world: World, caller: Caller, _current: object) -> dict[str, object]:
    body = room_body(world.room.department, f"room-{caller}")
    return {**body, "name": f"Room {caller}"}


def _service_created(world: World, caller: Caller, _current: object) -> dict[str, object]:
    body = service_body(world.room.department, f"intake-{caller}")
    return {**body, "name": f"Intake {caller}"}


def _renamed(_world: World, _caller: Caller, current: object) -> dict[str, object]:
    assert isinstance(current, dict)  # noqa: S101
    return {**current, "name": RENAMED}


def _concept_added(_world: World, _caller: Caller, current: object) -> dict[str, object]:
    assert isinstance(current, dict)  # noqa: S101
    concepts = current.get("concept", [])
    assert isinstance(concepts, list)  # noqa: S101
    listed = [*concepts, concept("cardiology", "Cardiology")]
    return {**current, "concept": listed, "count": len(listed)}


def _specialty_list(_world: World, _caller: Caller) -> str:
    # One record, shared by every caller: only the admin's write, sent last, changes it.
    return LIST_PATH


WRITE_CASES: tuple[WriteCase, ...] = (
    WriteCase(
        "Organization",
        "create",
        "",
        _collection("Organization"),
        _department_created,
        table=Department,
    ),
    WriteCase("Location", "create", "", _collection("Location"), _room_created, table=Room),
    WriteCase(
        "HealthcareService",
        "create",
        "",
        _collection("HealthcareService"),
        _service_created,
        table=AppointmentType,
    ),
    WriteCase("Organization", "update", "", _fresh_department, _renamed),
    WriteCase("Organization", "update", "hospital", _fresh_hospital, _renamed),
    WriteCase("Organization", "delete", "", _fresh_department, None, table=Department),
    WriteCase("Organization", "delete", "hospital", _fresh_hospital, None, table=Hospital),
    WriteCase("Location", "update", "", _fresh_room, _renamed),
    WriteCase("Location", "delete", "", _fresh_room, None, table=Room),
    WriteCase("HealthcareService", "update", "", _fresh_appointment_type, _renamed),
    WriteCase(
        "HealthcareService", "delete", "", _fresh_appointment_type, None, table=AppointmentType
    ),
    WriteCase("CodeSystem", "update", "", _specialty_list, _concept_added, reads_back=("concept",)),
)
