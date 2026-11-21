"""Conventions §5 size gate: a Python file over 500 lines or a function over 100 fails.
Generated migrations are exempt. Takes tracked paths as arguments."""

import ast
import sys
from pathlib import Path

MAXIMUM_FILE_LINES = 500
MAXIMUM_FUNCTION_LINES = 100
MIGRATIONS_SEGMENT = "/migrations/"


def size_violations(path: str, source: str) -> list[str]:
    if MIGRATIONS_SEGMENT in f"/{path}":
        return []
    violations = []
    file_lines = len(source.splitlines())
    if file_lines > MAXIMUM_FILE_LINES:
        violations.append(f"{path}: {file_lines} lines, limit {MAXIMUM_FILE_LINES}")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > MAXIMUM_FUNCTION_LINES:
                violations.append(
                    f"{path}:{node.lineno}: function {node.name} has {length} lines, "
                    f"limit {MAXIMUM_FUNCTION_LINES}"
                )
    return violations


def main(paths: list[str]) -> int:
    found = [
        violation
        for path in paths
        if path.endswith(".py")
        for violation in size_violations(path, Path(path).read_text(encoding="utf-8"))
    ]
    print("\n".join(found))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
