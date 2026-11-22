"""Task 24b, spec 15.4: an admin write body read as the fields of one console record. A reader
returns the values the console use cases take, or the dotted name of the first element it cannot
read. The field checks are the console's."""

from collections.abc import Callable, Mapping
from uuid import UUID

from scheduling.domain import record_fields
from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.fhir_body import Shape
from scheduling.domain.fhir_common import CODE_IDENTIFIER_SYSTEM, Resource, extension_url
from scheduling.domain.fhir_search import parse_id

type Values = dict[str, object]
type Entry = tuple[str, Result[object], str]

_CODING: Shape = {"coding": [{"system": str, "code": str, "display": str}]}
_REFERENCE: Shape = {"reference": str}
_META: Shape = {"versionId": str, "lastUpdated": str}
_IDENTIFIER: Shape = [{"system": str, "value": str}]
_EXTENSION: Shape = [
    {"url": str, "valueCode": str, "valueString": str, "valueInteger": int, "valueBoolean": bool}
]

ORGANIZATION_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": _META,
    "identifier": _IDENTIFIER,
    "active": bool,
    "type": [_CODING],
    "name": str,
    "partOf": _REFERENCE,
}
LOCATION_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": _META,
    "extension": _EXTENSION,
    "identifier": _IDENTIFIER,
    "status": str,
    "name": str,
    "telecom": [{"system": str, "value": str}],
    "address": {"line": [str], "city": str, "postalCode": str, "country": str},
    "physicalType": _CODING,
    "managingOrganization": _REFERENCE,
    "partOf": _REFERENCE,
    "position": {"longitude": float, "latitude": float},
}
SERVICE_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": _META,
    "extension": _EXTENSION,
    "identifier": _IDENTIFIER,
    "active": bool,
    "providedBy": _REFERENCE,
    "type": [{"text": str}],
    "specialty": [_CODING],
    "name": str,
}

# Built from other records: a body may repeat these, never change them. `type` of a service is
# its name again and is ignored.
DERIVED_ELEMENTS = {
    "hospital": ("managingOrganization",),
    "department": (),
    "room": ("partOf",),
    "appointment_type": ("specialty",),
}
# The body element each console field is read from, to name it in the answer to a refusal.
ELEMENT_OF_FIELD = {
    "hospital": {
        "name": "Location.name",
        "code": "Location.identifier",
        "is_active": "Location.status",
        "street_address": "Location.address.line",
        "city": "Location.address.city",
        "postal_code": "Location.address.postalCode",
        "country": "Location.address.country",
        "phone": "Location.telecom",
        "time_zone": "Location.extension",
        "latitude": "Location.position",
        "longitude": "Location.position",
    },
    "department": {
        "name": "Organization.name",
        "code": "Organization.identifier",
        "hospital": "Organization.partOf",
    },
    "room": {
        "name": "Location.name",
        "code": "Location.identifier",
        "is_active": "Location.status",
        "department": "Location.managingOrganization",
        "floor": "Location.extension",
        "capacity": "Location.extension",
        "equipment": "Location.extension",
    },
    "appointment_type": {
        "name": "HealthcareService.name",
        "code": "HealthcareService.identifier",
        "is_active": "HealthcareService.active",
        "department": "HealthcareService.providedBy",
        "duration_minutes": "HealthcareService.extension",
        "buffer_minutes": "HealthcareService.extension",
        "colour": "HealthcareService.extension",
        "needs_room": "HealthcareService.extension",
        "is_bookable_online": "HealthcareService.extension",
    },
}


def location_kind(body: Mapping[str, object]) -> str | None:
    """`hospital` for a site, `room` for a room, None for any other physical type."""
    return {"si": "hospital", "ro": "room"}.get(_coding_code(body.get("physicalType")))


def derived_difference(body: Mapping[str, object], stored: Mapping[str, object], kind: str) -> str:
    """The first derived element the body gives that the stored record does not have, or ''."""
    for name in DERIVED_ELEMENTS[kind]:
        if name in body and body[name] != stored.get(name):
            return name
    return ""


def organization_values(body: Resource) -> Values | str:
    if _first_coding_code(body.get("type")) != "dept":
        return "Organization.type"
    if body.get("active", True) is not True:
        return "Organization.active"
    values: Values = {"name": _text(body, "name"), "code": _code(body)}
    if "partOf" in body:
        parent = _reference_id(body.get("partOf"), "Organization")
        if parent is None:
            return "Organization.partOf"
        values["hospital_id"] = parent
    return values


def site_values(body: Resource) -> Values | str:
    if location_kind(body) != "hospital":
        return "Location.physicalType"
    status = _status(body)
    if not status:
        return "Location.status"
    address = body.get("address")
    place = address if isinstance(address, dict) else {}
    lines = place.get("line")
    line = str(lines[0]) if isinstance(lines, list) and lines else ""
    zone = _extension_value(body, "hospital-time-zone", "valueCode") or ""
    entries: list[Entry] = [
        _text_entry("street_address", line, 200, "a street address", "Location.address.line"),
        _text_entry("city", _text(place, "city"), 100, "a city", "Location.address.city"),
        _text_entry(
            "postal_code",
            _text(place, "postalCode"),
            20,
            "a postal code",
            "Location.address.postalCode",
        ),
        _text_entry(
            "country", _text(place, "country"), 100, "a country", "Location.address.country"
        ),
        _text_entry("phone", _telecom_phone(body), 30, "a phone number", "Location.telecom"),
        ("time_zone", Success(zone), "Location.extension"),
    ]
    values = _collected(entries)
    coordinates = _coordinates(body.get("position"))
    if isinstance(values, str):
        return values
    if isinstance(coordinates, str):
        return coordinates
    values["latitude"], values["longitude"] = coordinates
    return {**values, **_identity(body), "is_active": status == "active"}


def room_values(body: Resource) -> Values | str:
    if location_kind(body) != "room":
        return "Location.physicalType"
    status = _status(body)
    if not status:
        return "Location.status"
    parent = _reference_id(body.get("managingOrganization"), "Organization")
    if parent is None:
        return "Location.managingOrganization"
    floor = _extension_value(body, "room-floor", "valueString") or ""
    capacity = _extension_value(body, "room-capacity", "valueInteger")
    equipment = "\n".join(
        str(item) for item in _extension_values(body, "room-equipment", "valueString")
    )
    entries: list[Entry] = [
        _text_entry("floor", str(floor), 20, "a floor", "Location.extension"),
        ("capacity", record_fields.check_capacity(str(capacity)), "Location.extension"),
        ("equipment", record_fields.check_equipment(equipment), "Location.extension"),
    ]
    values = _collected(entries)
    if isinstance(values, str):
        return values
    return {**values, **_identity(body), "is_active": status == "active", "department_id": parent}


def service_values(body: Resource) -> Values | str:
    parent = _reference_id(body.get("providedBy"), "Organization")
    if parent is None:
        return "HealthcareService.providedBy"
    active = body.get("active")
    if not isinstance(active, bool):
        return "HealthcareService.active"
    duration = _extension_value(body, "service-duration-minutes", "valueInteger")
    buffer = _extension_value(body, "service-buffer-minutes", "valueInteger")
    colour = _extension_value(body, "service-colour", "valueString")
    extension_path = "HealthcareService.extension"
    entries: list[Entry] = [
        ("duration_minutes", record_fields.check_duration_minutes(str(duration)), extension_path),
        ("buffer_minutes", record_fields.check_buffer_minutes(str(buffer)), extension_path),
        ("colour", record_fields.check_colour(str(colour or "")), extension_path),
    ]
    values = _collected(entries)
    if isinstance(values, str):
        return values
    needs_room = _extension_value(body, "service-needs-room", "valueBoolean")
    bookable = _extension_value(body, "service-bookable-online", "valueBoolean")
    return {
        **values,
        **_identity(body),
        "is_active": active,
        "department_id": parent,
        "needs_room": needs_room is True,
        "is_bookable_online": bookable is True,
    }


VALUES_OF: dict[str, Callable[[Resource], Values | str]] = {
    "hospital": site_values,
    "department": organization_values,
    "room": room_values,
    "appointment_type": service_values,
}


def _identity(body: Resource) -> Values:
    return {"name": _text(body, "name"), "code": _code(body)}


def _collected(entries: list[Entry]) -> Values | str:
    values: Values = {}
    for field, checked, element in entries:
        if isinstance(checked, Failure):
            return element
        values[field] = checked.value
    return values


def _text_entry(field: str, raw: str, maximum: int, label: str, element: str) -> Entry:
    return field, record_fields.check_text(field, raw, maximum, f"Enter {label}."), element


def _status(body: Resource) -> str:
    status = body.get("status")
    return status if status in ("active", "inactive") else ""


def _text(source: Mapping[str, object], name: str) -> str:
    value = source.get(name)
    return value if isinstance(value, str) else ""


def _code(body: Resource) -> str:
    identifiers = body.get("identifier")
    for item in identifiers if isinstance(identifiers, list) else []:
        if item.get("system") == CODE_IDENTIFIER_SYSTEM:
            return _text(item, "value")
    return ""


def _telecom_phone(body: Resource) -> str:
    items = body.get("telecom")
    for item in items if isinstance(items, list) else []:
        if item.get("system") == "phone":
            return _text(item, "value")
    return ""


def _extension_values(body: Resource, name: str, key: str) -> list[object]:
    items = body.get("extension")
    return [
        item[key]
        for item in (items if isinstance(items, list) else [])
        if item.get("url") == extension_url(name) and key in item
    ]


def _extension_value(body: Resource, name: str, key: str) -> object:
    found = _extension_values(body, name, key)
    return found[0] if found else None


def _coordinates(position: object) -> tuple[float | None, float | None] | str:
    given = position if isinstance(position, dict) else {}
    latitude, longitude = given.get("latitude"), given.get("longitude")
    raw_latitude = "" if latitude is None else str(latitude)
    raw_longitude = "" if longitude is None else str(longitude)
    checked = record_fields.check_coordinates(raw_latitude, raw_longitude)
    return "Location.position" if isinstance(checked, Failure) else checked.value


def _reference_id(reference: object, resource_type: str) -> UUID | None:
    text = reference.get("reference") if isinstance(reference, dict) else None
    prefix = f"{resource_type}/"
    if not isinstance(text, str) or not text.startswith(prefix):
        return None
    parsed = parse_id(text.removeprefix(prefix))
    return UUID(parsed) if parsed is not None else None


def _coding_code(concept: object) -> str:
    codings = concept.get("coding") if isinstance(concept, dict) else None
    first = codings[0] if isinstance(codings, list) and codings else {}
    return _text(first, "code")


def _first_coding_code(concepts: object) -> str:
    return _coding_code(concepts[0]) if isinstance(concepts, list) and concepts else ""
