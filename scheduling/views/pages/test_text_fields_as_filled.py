"""Section 16: every post form the product renders, signed out and as each role. A
textarea takes `\\r\\n`, an empty line and a tab without a refusal; a one-line input refuses a
line break on that field and says it takes one line."""

from __future__ import annotations

import pytest

from scheduling.views.pages.admin_record_forms import FREE_TEXT_NAMES
from scheduling.views.pages.browser_support import browser_post
from scheduling.views.pages.form_walk_support import PageForm, post_forms
from scheduling.views.pages.page_walk_support import (
    ROLES,
    World,
    client_for_role,
    make_world,
    page_routes,
    path_of,
)

pytestmark = pytest.mark.django_db

PARAGRAPHS = "one\r\n\r\n\ttwo"
SAVED_PARAGRAPHS = "one\n\n\ttwo"
# Equipment is a list, one item a line: blank lines and tabs do not survive as items.
SAVED_AS_ITEMS = {"equipment": "one\ntwo"}
# A create form is posted with its other fields empty, so it may refuse for those; only the
# refusal sentence is checked there. Edit forms start filled and must save.
CREATE_SUFFIX = "/new"
LINE_BREAK = "a\nb"
ONE_LINE_SENTENCE = "This field takes one line."
REFUSAL_SENTENCE = "Remove the"
# Fields a person never saves as text, each with the reason it is not walked.
SKIPPED_FIELDS = {
    "q": "search box, a GET filter and not a write",
    "code": "the verification code: digits only, its own message",
    "password": "never echoed; the password rule has its own checks",
    "email": "an address, refused by the email rule with its own message",
    "link_email": "an address, refused by the email rule with its own message",
    "latitude": "a number: refused by the degrees rule, which names the range",
    "longitude": "a number: refused by the degrees rule, which names the range",
    "colour": "a hex colour: refused by the colour rule, which shows the format",
    "date_of_birth_day": "a number part of a date, refused by the date rule",
    "date_of_birth_month": "a number part of a date, refused by the date rule",
    "date_of_birth_year": "a number part of a date, refused by the date rule",
    "reason": "a one-line input that /api/v1 and FHIR take as free text; owner decision open",
}
SKIPPED_ON_FORM = {
    ("/patient/profile", "phone"): "digits and signs only; the phone rule names the allowed signs",
}


def _is_skipped(action: str, name: str) -> bool:
    return name in SKIPPED_FIELDS or (action, name) in SKIPPED_ON_FORM


def _walked(world: World) -> list[tuple[str, str, PageForm]]:
    found: dict[tuple[str, str], PageForm] = {}
    for route in page_routes():
        path = path_of(route, world)
        for role in ROLES:
            client = client_for_role(role, world)
            response = client.get(path)
            if response.status_code != 200:
                continue
            for form in post_forms(response.content.decode(), path):
                found.setdefault((role, form.action), form)
    return [(role, action, form) for (role, action), form in found.items()]


def _sent(world: World, role: str, form: PageForm, name: str, text: str) -> str:
    client = client_for_role(role, world)
    page = browser_post(client, form.action, {**form.values, name: text})
    return page.content.decode()


def _read_back(world: World, role: str, form: PageForm, name: str) -> str | None:
    page = client_for_role(role, world).get(form.page_path)
    for shown in post_forms(page.content.decode(), form.page_path):
        if shown.action == form.action and name in shown.textareas:
            return shown.values[name].replace("\r\n", "\n").strip()
    return None


def returns_no_refusal_when_a_textarea_gets_paragraphs_and_a_tab() -> None:
    world = make_world()
    walked = _walked(world)
    textareas = saved = 0
    problems: list[str] = []
    for role, action, form in walked:
        for name in form.textareas:
            textareas += 1
            if _is_skipped(action, name):
                continue
            client = client_for_role(role, world)
            response = browser_post(client, action, {**form.values, name: PARAGRAPHS})
            page = response.content.decode()
            refused = ONE_LINE_SENTENCE in page or REFUSAL_SENTENCE in page
            if refused:
                problems.append(f"{role} {action} {name} refused the text")
            elif action.endswith(CREATE_SUFFIX):
                continue
            elif response.status_code != 303:
                problems.append(f"{role} {action} {name} answered {response.status_code}")
            elif _read_back(world, role, form, name) != SAVED_AS_ITEMS.get(name, SAVED_PARAGRAPHS):
                problems.append(f"{role} {action} {name} not read back")
            else:
                saved += 1
    assert textareas >= 4
    assert saved >= 4
    assert problems == [], "\n".join(problems)


def returns_one_line_message_when_a_text_input_gets_a_line_break() -> None:
    world = make_world()
    walked = _walked(world)
    inputs = 0
    problems: list[str] = []
    for role, action, form in walked:
        for name in form.text_inputs:
            if _is_skipped(action, name):
                continue
            inputs += 1
            if ONE_LINE_SENTENCE not in _sent(world, role, form, name, LINE_BREAK):
                problems.append(f"{role} {action} {name}")
    assert inputs >= 10
    assert problems == [], "\n".join(problems)


def returns_every_declared_textarea_walked_when_the_forms_render() -> None:
    world = make_world()
    walked = {name for _role, _action, form in _walked(world) for name in form.textareas}

    assert walked >= FREE_TEXT_NAMES
