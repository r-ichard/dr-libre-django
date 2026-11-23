"""Writes the access section of doc/security-review.md from the three access tables.

Run from the repository root: `make access-table`. Stdlib only; the tables import no Django.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from scheduling.views.pages import (
    test_page_access_rows,
    test_page_access_rows_admin,
    test_page_access_rows_admin_operations,
    test_page_access_rows_clinician,
    test_page_access_rows_patient,
)
from scheduling.views.pages.test_page_access_rows import Answer, Caller, Row
from scheduling.views.test_api_access_rows import (
    API_ACCESS_ROWS,
    AccessRow,
    KnownDifference,
)
from scheduling.views.test_api_access_rows import (
    KNOWN_DIFFERENCES as API_KNOWN_DIFFERENCES,
)
from test_support.fhir_access_rows import (
    FHIR_ACCESS_ROWS,
    FhirAccessRow,
)
from test_support.fhir_access_rows import (
    KNOWN_DIFFERENCES as FHIR_KNOWN_DIFFERENCES,
)
from test_support.fhir_access_rows import (
    KnownDifference as FhirKnownDifference,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_PATH = REPO_ROOT / "doc" / "security-review.md"
ACCESS_HEADING = "## Access"
PAGE_ROW_MODULES: tuple[ModuleType, ...] = (
    test_page_access_rows,
    test_page_access_rows_admin,
    test_page_access_rows_admin_operations,
    test_page_access_rows_clinician,
    test_page_access_rows_patient,
)
PageDifferenceKey = tuple[str, Caller]
PageDifferenceValue = tuple[Answer, str]


@dataclass(frozen=True)
class AccessTables:
    api_rows: tuple[AccessRow, ...]
    api_differences: tuple[KnownDifference, ...]
    page_rows: tuple[Row, ...]
    page_differences: Mapping[PageDifferenceKey, PageDifferenceValue]
    fhir_rows: tuple[FhirAccessRow, ...]
    fhir_differences: tuple[FhirKnownDifference, ...]


def current_tables() -> AccessTables:
    return AccessTables(
        api_rows=API_ACCESS_ROWS,
        api_differences=API_KNOWN_DIFFERENCES,
        page_rows=(
            test_page_access_rows.NO_SESSION_ROWS
            + test_page_access_rows_patient.PATIENT_ROWS
            + test_page_access_rows_clinician.CLINICIAN_ROWS
            + test_page_access_rows_admin.ADMIN_RECORD_ROWS
            + test_page_access_rows_admin_operations.ADMIN_OPERATION_ROWS
            + test_page_access_rows.STYLE_ROWS
        ),
        page_differences=test_page_access_rows.KNOWN_DIFFERENCES,
        fhir_rows=FHIR_ACCESS_ROWS,
        fhir_differences=FHIR_KNOWN_DIFFERENCES,
    )


def _paragraphs(*paragraphs: str) -> str:
    return "\n\n".join(paragraphs)


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def _path(stored_route: str) -> str:
    return f"`/{stored_route}`"


def _differences(bullets: Sequence[str]) -> str:
    if not bullets:
        return "Known differences: none."
    return "Known differences:\n\n" + "\n".join(bullets)


def _api_bullet(difference: KnownDifference) -> str:
    subject = difference.caller.value
    if difference.record is not None:
        subject += f", {difference.record.value} record"
    return (
        f"- `{difference.method} /{difference.route}`, {subject}: "
        f"table `{difference.row_answer}`, product `{difference.product_answer}`."
    )


def render_api_table(rows: Sequence[AccessRow], differences: Sequence[KnownDifference]) -> str:
    table = _table(
        ("Method", "Route", "Visitor", "Patient", "Clinician", "Admin", "Basis"),
        [
            (
                row.method,
                _path(row.route),
                str(row.visitor),
                str(row.patient),
                str(row.clinician),
                str(row.admin),
                row.basis,
            )
            for row in rows
        ],
    )
    bullets = [_api_bullet(difference) for difference in differences]
    return _paragraphs("### API (`/api/v1`)", table, _differences(bullets))


def _page_bullet(key: PageDifferenceKey, value: PageDifferenceValue) -> str:
    (route, caller), (table_answer, product_answer) = key, value
    return f"- `/{route}`, {caller}: table `{table_answer}`, product `{product_answer}`."


def render_page_table(
    rows: Sequence[Row],
    differences: Mapping[PageDifferenceKey, PageDifferenceValue],
) -> str:
    table = _table(
        ("Route", "Visitor", "Patient", "Clinician", "Admin", "Names a record", "Debug only"),
        [
            (
                _path(row.route),
                row.visitor,
                row.patient,
                row.clinician,
                row.admin,
                "yes" if row.names_record else "no",
                "yes" if row.debug_only else "no",
            )
            for row in rows
        ],
    )
    bullets = [_page_bullet(key, value) for key, value in differences.items()]
    return _paragraphs("### Pages", table, _differences(bullets))


def _fhir_bullet(difference: FhirKnownDifference) -> str:
    return (
        f"- `{difference.resource} {difference.interaction}`, {difference.caller.value}: "
        f"table `{difference.row_answer}`, product `{difference.product_answer}`."
    )


def render_fhir_table(
    rows: Sequence[FhirAccessRow],
    differences: Sequence[FhirKnownDifference],
) -> str:
    table = _table(
        ("Resource", "Interaction", "No token", "Patient", "Clinician", "Admin", "Basis"),
        [
            (
                row.resource,
                row.interaction,
                str(row.visitor),
                str(row.patient),
                str(row.clinician),
                str(row.admin),
                row.basis,
            )
            for row in rows
        ],
    )
    bullets = [_fhir_bullet(difference) for difference in differences]
    return _paragraphs("### FHIR (`/fhir`)", table, _differences(bullets))


INTRO = (
    "Generated by `make access-table` from the three access tables; do not edit by hand. "
    "`scripts/test_access_table.py` fails when this text differs from the output. "
    "Cells: HTTP status for API and FHIR; `ok`, `sign-in`, `forbidden`, `not-found` for pages."
)


def render_section(tables: AccessTables) -> str:
    return (
        _paragraphs(
            ACCESS_HEADING,
            INTRO,
            render_api_table(tables.api_rows, tables.api_differences),
            render_page_table(tables.page_rows, tables.page_differences),
            render_fhir_table(tables.fhir_rows, tables.fhir_differences),
        )
        + "\n\n"
    )


def splice(document: str, section: str) -> str:
    lines = document.splitlines(keepends=True)
    headings = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == ACCESS_HEADING]
    if len(headings) != 1:
        raise ValueError(f"expected one '{ACCESS_HEADING}' heading, found {len(headings)}")
    start = headings[0]
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return "".join(lines[:start]) + section + "".join(lines[end:])


def main() -> None:
    document = REVIEW_PATH.read_text(encoding="utf-8")
    REVIEW_PATH.write_text(splice(document, render_section(current_tables())), encoding="utf-8")


if __name__ == "__main__":
    main()
