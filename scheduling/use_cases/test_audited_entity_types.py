"""Task 21, item 14: a record type the product audits can always be filtered in the audit log.
The source is read, so a new audited type with no entry in the registry fails here."""

import ast
from pathlib import Path

from scheduling.domain.audit_entity_types import AUDITED_ENTITY_TYPES

SCHEDULING = Path(__file__).resolve().parent.parent
AUDITING_CALLS = {"AuditEvent", "_audit"}


def _is_type_name(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value[:1].isupper()
    )


def _audited_literals(source: str) -> set[str]:
    tree = ast.parse(source)
    constants = {
        target.id: node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    found: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id not in AUDITING_CALLS or len(node.args) < 2:
            continue
        second = node.args[1]
        # Another `_audit` helper takes a verb here; a record type starts with a capital.
        if (
            isinstance(second, ast.Constant)
            and isinstance(second.value, str)
            and second.value[:1].isupper()
        ):
            found.add(second.value)
        elif isinstance(second, ast.Name) and isinstance(constants.get(second.id), str):
            found.add(str(constants[second.id]))
    return found


def returns_every_literal_audited_type_in_the_registry_when_the_source_is_read() -> None:
    audited: set[str] = set()
    for path in SCHEDULING.rglob("*.py"):
        if not path.name.startswith("test_"):
            audited |= _audited_literals(path.read_text())

    assert audited
    assert audited - AUDITED_ENTITY_TYPES == set()


def returns_the_unlisted_type_when_the_source_audits_one() -> None:
    assert _audited_literals('AuditEvent("x.y", "BrandNewType", "1", metadata)') == {"BrandNewType"}
