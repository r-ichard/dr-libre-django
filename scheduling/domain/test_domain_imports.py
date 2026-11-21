"""Section 8: the domain layer is pure, so it imports no Django and no outer layer."""

import ast
from pathlib import Path

FORBIDDEN_PREFIXES = ("django", "scheduling.models", "scheduling.use_cases", "scheduling.views")
DOMAIN_DIRECTORY = Path(__file__).parent


def _imported_modules(source_file: Path) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(ast.parse(source_file.read_text())):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return modules


def _is_forbidden(module: str) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_PREFIXES)


def returns_no_forbidden_imports_when_domain_modules_are_parsed() -> None:
    offenders = [
        f"{source_file.name} imports {module}"
        for source_file in sorted(DOMAIN_DIRECTORY.glob("*.py"))
        if not source_file.name.startswith("test_")
        for module in _imported_modules(source_file)
        if _is_forbidden(module)
    ]
    assert offenders == []
