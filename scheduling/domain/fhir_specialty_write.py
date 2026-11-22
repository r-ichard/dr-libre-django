"""Task 24b2, spec 15.4: a PUT of the specialty CodeSystem is the whole list. This reads the body
into concepts and diffs them against the stored list; the use case applies the changes."""

import re
from dataclasses import dataclass
from uuid import UUID

from scheduling.domain.fhir_body import Shape
from scheduling.domain.fhir_common import SPECIALTY_SYSTEM
from scheduling.domain.fhir_specialty import INACTIVE_CODE, INACTIVE_DECLARATION

ROOT = "CodeSystem"
CODE_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,50}")
CODE_SYSTEM_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": {"versionId": str, "lastUpdated": str},
    "url": str,
    "name": str,
    "status": str,
    "content": str,
    "caseSensitive": bool,
    "property": [{"code": str, "uri": str, "type": str}],
    "count": int,
    "concept": [{"code": str, "display": str, "property": [{"code": str, "valueBoolean": bool}]}],
}
# Elements the server builds; a body that sends one must send the value the server would.
BUILT_ELEMENTS: dict[str, object] = {
    "url": SPECIALTY_SYSTEM,
    "name": "DrLibreSpecialty",
    "status": "active",
    "content": "complete",
    "caseSensitive": False,
    "property": [INACTIVE_DECLARATION],
}


@dataclass(frozen=True)
class Concept:
    index: int
    code: str
    display: str
    inactive: bool


@dataclass(frozen=True)
class StoredConcept:
    key: UUID
    code: str
    name: str
    is_active: bool


@dataclass(frozen=True)
class Change:
    """`stored` is None for an add, `concept` is None for a removal."""

    stored: StoredConcept | None
    concept: Concept | None


def desired_concepts(body: dict[str, object]) -> tuple[Concept, ...] | str:
    """The concepts the body lists, or the dotted name of the element that is wrong."""
    for name, built in BUILT_ELEMENTS.items():
        if name in body and body[name] != built:
            return f"{ROOT}.{name}"
    raw = body.get("concept", [])
    if not isinstance(raw, list):
        return f"{ROOT}.concept"
    if "count" in body and body["count"] != len(raw):
        return f"{ROOT}.count"
    concepts: list[Concept] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        found = _concept(index, item)
        if isinstance(found, str):
            return found
        if found.code.lower() in seen:
            return f"{ROOT}.concept[{index}].code"
        seen.add(found.code.lower())
        concepts.append(found)
    return tuple(concepts)


def _concept(index: int, item: object) -> Concept | str:
    if not isinstance(item, dict):
        return f"{ROOT}.concept[{index}]"
    code = item.get("code")
    if not isinstance(code, str) or CODE_PATTERN.fullmatch(code) is None:
        return f"{ROOT}.concept[{index}].code"
    display = item.get("display")
    if not isinstance(display, str) or not display.strip():
        return f"{ROOT}.concept[{index}].display"
    inactive = _inactive(item.get("property", []))
    if inactive is None:
        return f"{ROOT}.concept[{index}].property"
    return Concept(index, code, display, inactive)


def _inactive(properties: object) -> bool | None:
    """None when a property is not the one declared: `inactive` with a boolean, at most once."""
    if not isinstance(properties, list) or len(properties) > 1:
        return None
    if not properties:
        return False
    only = properties[0]
    if not isinstance(only, dict) or only.get("code") != INACTIVE_CODE:
        return None
    if set(only) != {"code", "valueBoolean"} or not isinstance(only["valueBoolean"], bool):
        return None
    return only["valueBoolean"]


def plan_changes(
    stored: tuple[StoredConcept, ...], desired: tuple[Concept, ...]
) -> tuple[tuple[Change, ...], tuple[Change, ...], tuple[Change, ...]]:
    """Removals, then edits, then adds, so a code a removal frees can be taken in the same body.
    Concepts match stored specialties by code, ignoring case."""
    wanted = {concept.code.lower(): concept for concept in desired}
    kept = {row.code.lower(): row for row in stored}
    removals = tuple(Change(row, None) for row in stored if row.code.lower() not in wanted)
    edits = tuple(
        Change(kept[key], concept)
        for key, concept in wanted.items()
        if key in kept and _differs(kept[key], concept)
    )
    adds = tuple(Change(None, concept) for key, concept in wanted.items() if key not in kept)
    return removals, edits, adds


def _differs(row: StoredConcept, concept: Concept) -> bool:
    return row.name != concept.display.strip() or row.is_active == concept.inactive
