"""Product code never imports the test-only support package."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCT_ROOTS = ("drlibre", "scheduling")
SUPPORT_PACKAGE = "test_support"


def _is_product_file(path: Path) -> bool:
    return not path.name.startswith("test_") and path.name != "conftest.py"


def _imported_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    return [node.module or ""]


def _names_support(name: str) -> bool:
    return name == SUPPORT_PACKAGE or name.startswith(f"{SUPPORT_PACKAGE}.")


def _support_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            names = _imported_names(node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names = [node.value]  # a dotted string such as a ROOT_URLCONF is an import too
        else:
            continue
        if any(_names_support(name) for name in names):
            hits.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    return hits


def returns_no_product_module_importing_test_support() -> None:
    product_files = [
        path
        for package in PRODUCT_ROOTS
        for path in (ROOT / package).rglob("*.py")
        if _is_product_file(path)
    ]

    offenders = [hit for path in product_files for hit in _support_imports(path)]

    assert offenders == []
