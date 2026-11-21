"""Task 10a: vendored icons with their source recorded, and the spacing the booking pages need."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ICON_DIRECTORY = ROOT / "static" / "icons" / "specialties"
BOOKING_TEMPLATES = ROOT / "scheduling" / "templates" / "booking"


def returns_fallback_icon_and_source_with_revision_and_licence_when_icons_are_vendored() -> None:
    source = (ICON_DIRECTORY / "SOURCE.md").read_text()

    assert (ICON_DIRECTORY / "fallback.svg").is_file()
    assert "healthicons.org" in source
    assert "revision" in source.lower()
    assert "CC0" in source


def returns_button_row_class_on_booking_confirmation_buttons() -> None:
    template = (BOOKING_TEMPLATES / "confirmation.html").read_text()

    assert 'class="button-row"' in template


def returns_spacing_tokens_for_stacked_blocks_and_button_row_in_base_css() -> None:
    css = (ROOT / "static" / "css" / "base.css").read_text()

    stacked = re.search(r"\.page > \.notice[^{]*\{([^}]*)\}", css)
    row = re.search(r"\.button-row \{([^}]*)\}", css)
    assert stacked is not None
    assert "margin-block: var(--space-4)" in stacked.group(1)
    assert row is not None
    assert "gap: var(--space-3)" in row.group(1)
