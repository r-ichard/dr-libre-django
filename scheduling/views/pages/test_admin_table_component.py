"""Task 25c, item 1: every admin table is one component. Wrappers are keyboard-reachable and
labelled by their caption; each cell names its column for the card layout under 40rem."""

import re
from pathlib import Path

import pytest

from scheduling.models.builders import make
from scheduling.views.pages.admin_support import admin_client

pytestmark = pytest.mark.django_db

CONSOLE = "/admin-console"
LISTS = ["hospitals", "specialties", "departments", "rooms", "appointment-types", "users",
         "clinicians"]  # fmt: skip
CSS = Path(__file__).resolve().parents[3] / "static" / "css" / "components.css"
SMALL_FRAME_PX = 341


def _seed() -> None:
    for model in (
        "Hospital",
        "Specialty",
        "Department",
        "Room",
        "AppointmentType",
        "ClinicianProfile",
        "Appointment",
    ):
        make(model)


def _pages() -> dict[str, str]:
    _seed()
    client = admin_client()
    return {
        path: client.get(f"{CONSOLE}/{path}").content.decode()
        for path in [*LISTS, "", "waitlist", "audit", "appointments"]
    }


def _wrappers(html: str) -> list[str]:
    return re.findall(r"<div class=\"table-wrap\"[^>]*>", html)


def returns_every_labelled_wrapper_when_any_table_page_is_rendered() -> None:
    counted = 0
    for path, html in _pages().items():
        for wrapper in _wrappers(html):
            counted += 1
            assert 'tabindex="0"' in wrapper, path
            assert 'role="region"' in wrapper, path
            label = re.search(r'aria-labelledby="([^"]+)"', wrapper)
            assert label, path
            assert re.search(rf'<caption[^>]*id="{label.group(1)}"', html), path
            assert "aria-label=" not in wrapper, path
    assert counted >= len(LISTS) + 1


def returns_a_data_label_on_every_cell_when_a_list_is_rendered() -> None:
    for path, html in _pages().items():
        for table in re.findall(r"<table.*?</table>", html, re.S):
            headers = re.findall(r"<th[^>]*scope=\"col\"[^>]*>(.*?)</th>", table, re.S)
            body = table.split("<tbody", 1)[1] if "<tbody" in table else ""
            for row in re.findall(r"<tr.*?</tr>", body, re.S):
                cells = re.findall(r"<t[hd]\b[^>]*>", row)
                labels = [re.search(r'data-label="([^"]*)"', cell) for cell in cells]
                assert all(labels), path
                assert [found.group(1) for found in labels if found] == [
                    header.strip() for header in headers
                ][: len(labels)], path


def returns_the_same_wrapper_class_and_table_class_when_every_admin_list_is_rendered() -> None:
    pages = _pages()

    shapes = {re.sub(r'aria-labelledby="[^"]*"', "", _wrappers(pages[path])[0]) for path in LISTS}

    assert len(shapes) == 1


def returns_card_rules_under_40rem_when_the_stylesheet_is_read() -> None:
    css = CSS.read_text()
    block = css.split("@media (max-width: 39.99rem)", 1)[1].split("\n}\n", 1)[0]

    for part in ("table", "tbody", "tr", "td", "th"):
        assert re.search(rf"\.table {part}\b[^{{]*{{[^}}]*display: block", block), part
    assert re.search(r"td::before[^{]*{[^}]*content: attr\(data-label\)", block)
    assert "white-space: normal" in block
    assert "overflow-wrap: anywhere" in block
    pixels = [int(found) for found in re.findall(r"(?:min-)?width: (\d+)px", block)]
    assert all(pixel <= SMALL_FRAME_PX for pixel in pixels)
