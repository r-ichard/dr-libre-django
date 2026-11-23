"""Module docstrings do not open with a task number, so each one says what it holds."""

import ast
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SCANNED_ROOTS = ("scheduling", "drlibre", "test_support")
TASK_NUMBER_OPENING = re.compile(r"Task \d")


def returns_no_task_numbered_module_docstrings_when_modules_are_parsed() -> None:
    offenders: list[str] = []
    for root_name in SCANNED_ROOTS:
        root = REPOSITORY_ROOT / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            docstring = ast.get_docstring(tree, clean=False) or ""
            if TASK_NUMBER_OPENING.match(docstring):
                offenders.append(str(path.relative_to(REPOSITORY_ROOT)))
    assert not offenders, "module docstrings open with a task number: " + ", ".join(offenders)
