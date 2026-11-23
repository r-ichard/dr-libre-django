"""Section 10: a save over a newer version shows field by field what the admin read, what
is stored now and what the admin typed. As a browser posts: cross-site check on, `Origin` set."""

import re

import pytest

from scheduling.models import Hospital
from scheduling.models.builders import make
from scheduling.views.pages.admin_support import admin_client, admin_post
from scheduling.views.pages.test_admin_records_pages import CONSOLE, HOSPITAL_FORM

pytestmark = pytest.mark.django_db


def _stale_save(read_name: str | None) -> str:
    hospital = make("Hospital", name="Before")
    assert isinstance(hospital, Hospital)
    client = admin_client()
    path = f"{CONSOLE}/hospitals/{hospital.pk}/edit"
    first = {**HOSPITAL_FORM, "code": hospital.code, "name": "First admin", "version": "1"}
    assert admin_post(client, path, first).status_code == 303
    second = {**first, "name": "Second admin"}
    if read_name is not None:
        second["read_name"] = read_name
    response = admin_post(client, path, second)
    assert response.status_code == 409
    return response.content.decode()


def _block(html: str) -> str:
    assert "What differs" in html
    return html.split("What differs", 1)[1].split("</fieldset>", 1)[0]


def returns_the_changed_field_with_three_values_when_the_save_is_stale() -> None:
    block = _block(_stale_save("Before"))

    assert re.search(r"You read\s*</dt>\s*<dd[^>]*>\s*Before\s*</dd>", block)
    assert re.search(r"Now stored\s*</dt>\s*<dd[^>]*>\s*First admin\s*</dd>", block)
    assert re.search(r"You typed\s*</dt>\s*<dd[^>]*>\s*Second admin\s*</dd>", block)


def returns_not_known_for_the_read_value_when_the_form_posts_no_read_field() -> None:
    block = _block(_stale_save(None))

    assert "Not known: this form did not keep it" in block


def returns_no_row_for_a_field_that_nobody_changed() -> None:
    block = _block(_stale_save("Before"))

    assert "Phone" not in block
    assert block.count("You typed") == 1


def returns_escaped_read_text_when_the_read_field_holds_markup() -> None:
    html = _stale_save("<script>alert(1)</script>")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in _block(html)


def returns_the_choice_in_words_when_the_save_is_stale() -> None:
    html = _stale_save("Before")

    assert "Save again to replace the stored values with yours" in html
    assert "Saving again replaces theirs" not in html


def returns_refreshed_read_fields_when_the_stale_page_is_shown() -> None:
    html = _stale_save("Before")

    assert re.search(r'name="read_name"[^>]*value="First admin"', html)
