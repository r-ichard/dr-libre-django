"""Task 17c, #27: every audit action the product writes has plain words in the history."""

import ast
import re
from pathlib import Path

from scheduling.domain.audit_labels import AUDIT_LABELS

PACKAGE = Path(__file__).resolve().parent.parent
ACTION_SHAPE = re.compile(r"^[a-z_]+\.[a-z_]+$")
LOGGER_NAMES = {"drlibre.mail", "scheduling.jobs"}
SOURCE_DIRECTORIES = ("use_cases", "demo_seed", "jobs")


def _written_actions() -> set[str]:
    found: set[str] = set()
    for directory in SOURCE_DIRECTORIES:
        for source in (PACKAGE / directory).rglob("*.py"):
            if source.name.startswith("test_"):
                continue
            for node in ast.walk(ast.parse(source.read_text())):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and ACTION_SHAPE.match(node.value)
                    and node.value not in LOGGER_NAMES
                ):
                    found.add(node.value)
    return found


def returns_plain_words_when_the_product_writes_any_audit_action() -> None:
    written = _written_actions()

    unlabelled = sorted(action for action in written if action not in AUDIT_LABELS)

    assert len(written) > 30
    assert unlabelled == []


def returns_no_dotted_code_when_a_label_is_shown() -> None:
    assert [action for action, label in AUDIT_LABELS.items() if "." in label] == []
