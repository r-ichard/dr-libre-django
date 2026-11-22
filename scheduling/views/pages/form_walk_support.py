"""The post forms of a rendered page, read as a browser reads them: every named field with the
value it starts with, so a test can change one field and send the rest as they came."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

TEXT_INPUT_TYPES = ("text", "search", "tel", "email", "url")
NOT_SENT_TYPES = ("submit", "button", "image", "reset", "file")


@dataclass
class PageForm:
    action: str
    page_path: str = ""
    values: dict[str, str] = field(default_factory=dict)
    textareas: list[str] = field(default_factory=list)
    text_inputs: list[str] = field(default_factory=list)


class _FormReader(HTMLParser):
    def __init__(self, page_path: str) -> None:
        super().__init__()
        self.page_path = page_path
        self.forms: list[PageForm] = []
        self._open_textarea = ""
        self._open_select = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = {key: value or "" for key, value in attrs}
        if tag == "form" and found.get("method", "get").lower() == "post":
            self.forms.append(PageForm(found.get("action") or self.page_path, self.page_path))
        elif not self.forms:
            return
        elif tag == "input":
            self._input(found)
        elif tag == "textarea":
            self._open_textarea = found.get("name", "")
            self._add_textarea(self._open_textarea)
        elif tag == "select":
            self._open_select = found.get("name", "")
        elif tag == "option" and self._open_select:
            self._option(found)

    def handle_endtag(self, tag: str) -> None:
        if tag == "textarea":
            self._open_textarea = ""
        elif tag == "select":
            self._open_select = ""

    def handle_data(self, data: str) -> None:
        if self._open_textarea:
            self.forms[-1].values[self._open_textarea] += data

    def _add_textarea(self, name: str) -> None:
        if name:
            self.forms[-1].textareas.append(name)
            self.forms[-1].values[name] = ""

    def _input(self, found: dict[str, str]) -> None:
        name, kind = found.get("name", ""), found.get("type", "text").lower()
        current = self.forms[-1]
        if not name or kind in NOT_SENT_TYPES or "disabled" in found:
            return
        if kind in ("checkbox", "radio") and "checked" not in found:
            return
        current.values[name] = found.get("value", "")
        if kind in TEXT_INPUT_TYPES:
            current.text_inputs.append(name)

    def _option(self, found: dict[str, str]) -> None:
        values = self.forms[-1].values
        if self._open_select not in values or "selected" in found:
            values[self._open_select] = found.get("value", "")


def post_forms(html: str, page_path: str) -> list[PageForm]:
    reader = _FormReader(page_path)
    reader.feed(html)
    return reader.forms
