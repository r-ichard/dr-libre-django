"""Task 24b2: request bodies and helpers the specialty list write tests share."""

from scheduling.models import AuditLogEntry, Specialty
from scheduling.models.builders import make
from scheduling.views.fhir_test_support import get

LIST_PATH = "/fhir/CodeSystem/specialty"
INACTIVE_PROPERTY = [{"code": "inactive", "valueBoolean": True}]


def concept(code: str, display: str, inactive: bool = False) -> dict[str, object]:
    found: dict[str, object] = {"code": code, "display": display}
    if inactive:
        found["property"] = INACTIVE_PROPERTY
    return found


def stored(code: str, name: str, is_active: bool = True) -> Specialty:
    row = make("Specialty", code=code, name=name, is_active=is_active)
    assert isinstance(row, Specialty)  # noqa: S101
    return row


def current_list(token: str) -> dict[str, object]:
    body = get(LIST_PATH, token).json()
    assert isinstance(body, dict)  # noqa: S101
    return body


def concepts_of(token: str) -> list[dict[str, object]]:
    listed = current_list(token).get("concept", [])
    assert isinstance(listed, list)  # noqa: S101
    return listed


def with_concepts(token: str, *concepts: dict[str, object]) -> dict[str, object]:
    """The list as the admin reads it, its concepts replaced; derived elements recomputed."""
    body = current_list(token)
    body["concept"] = list(concepts)
    body["count"] = len(concepts)
    return body


def concept_codes(token: str) -> list[str]:
    return [str(item["code"]) for item in concepts_of(token)]


def specialty_audit() -> list[tuple[str, str]]:
    written = AuditLogEntry.objects.filter(entity_type="Specialty").order_by("created_at")
    return [(entry.action, entry.entity_id) for entry in written]
