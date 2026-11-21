import ast
from pathlib import Path

SCANNED_PACKAGES = ["domain", "use_cases"]
FORBIDDEN_CALLS = {"datetime.now", "datetime.utcnow", "time.time", "timezone.now", "date.today"}
SCHEDULING_ROOT = Path(__file__).resolve().parent.parent


def _wall_clock_reads(source: str) -> list[str]:
    reads = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if isinstance(owner, ast.Name) and f"{owner.id}.{node.func.attr}" in FORBIDDEN_CALLS:
                reads.append(f"{owner.id}.{node.func.attr}")
    return reads


def returns_the_read_when_source_calls_datetime_now() -> None:
    assert _wall_clock_reads("import datetime\nx = datetime.now()") == ["datetime.now"]


def returns_no_wall_clock_read_when_domain_and_use_case_sources_are_scanned() -> None:
    offences = []
    for package in SCANNED_PACKAGES:
        for path in (SCHEDULING_ROOT / package).rglob("*.py"):
            offences += [f"{path.name}: {read}" for read in _wall_clock_reads(path.read_text())]

    assert offences == []
