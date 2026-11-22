"""Section 16 checks over rendered HTML: what a screen reader or a keyboard user would meet.
Pure text in, a list of findings out, so a test can name the page that broke."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

UNLABELLED_INPUT_TYPES = {"hidden", "submit", "button", "image", "reset"}
TITLE_LIMIT = 80
TOKEN_FIELD = "csrfmiddlewaretoken"  # noqa: S105 - a field name, not a secret
VOID_TAGS = {"input", "img", "br", "meta", "link", "hr"}


@dataclass
class _Control:
    kind: str
    attributes: dict[str, str]
    text: str = ""


@dataclass
class _Table:
    has_header_cell: bool = False


@dataclass
class _Collected:
    ids: list[str] = field(default_factory=list)
    label_targets: set[str] = field(default_factory=set)
    fields: list[tuple[dict[str, str], bool]] = field(default_factory=list)
    controls: list[_Control] = field(default_factory=list)
    headings: list[int] = field(default_factory=list)
    images_without_alternative: int = 0
    tables: list[_Table] = field(default_factory=list)
    title: str = ""
    title_markup: bool = False
    token_outside_form: bool = False
    has_lang: bool = False
    has_main: bool = False


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.found = _Collected()
        self._open_elements: list[_Control] = []
        self._label_depth = 0
        self._hidden_depth = 0
        self._in_title = False
        self._form_depth = 0
        self._tables: list[_Table] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if "id" in attributes:
            self.found.ids.append(attributes["id"])
        if tag == "html":
            self.found.has_lang = bool(attributes.get("lang"))
        if tag == "main":
            self.found.has_main = True
        if tag == "title":
            self._in_title = True
        if tag == "form":
            self._form_depth += 1
        if attributes.get("name") == TOKEN_FIELD and self._form_depth == 0:
            self.found.token_outside_form = True
        if tag == "label":
            self._label_depth += 1
            if "for" in attributes:
                self.found.label_targets.add(attributes["for"])
        if tag in {"input", "select", "textarea"}:
            wrapped = self._label_depth > 0
            if attributes.get("type", "text") not in UNLABELLED_INPUT_TYPES:
                self.found.fields.append((attributes, wrapped))
        if tag == "img" and "alt" not in attributes:
            self.found.images_without_alternative += 1
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.found.headings.append(int(tag[1]))
        if tag == "table":
            table = _Table()
            self._tables.append(table)
            self.found.tables.append(table)
        if tag == "th" and self._tables:
            self._tables[-1].has_header_cell = True
        if attributes.get("aria-hidden") == "true" and tag not in VOID_TAGS:
            self._hidden_depth += 1
            self._open_elements.append(_Control("hidden", {}))
        elif tag in {"a", "button"}:
            self._open_elements.append(_Control(tag, attributes))
        elif tag not in VOID_TAGS:
            self._open_elements.append(_Control(f"other:{tag}", {}))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "form":
            self._form_depth = max(0, self._form_depth - 1)
        if tag == "label":
            self._label_depth = max(0, self._label_depth - 1)
        if tag == "table" and self._tables:
            self._tables.pop()
        while self._open_elements:
            control = self._open_elements.pop()
            if control.kind == "hidden":
                self._hidden_depth -= 1
            if control.kind in {"a", "button"}:
                self.found.controls.append(control)
            if control.kind in {"hidden", "a", "button"} or control.kind == f"other:{tag}":
                break

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.found.title += data
            self.found.title_markup = self.found.title_markup or "<" in data
        if self._hidden_depth == 0:
            for control in self._open_elements:
                control.text += data


def _unlabelled_fields(found: _Collected) -> list[str]:
    names = []
    for attributes, wrapped in found.fields:
        named = attributes.get("aria-label") or attributes.get("aria-labelledby")
        if not (named or wrapped or attributes.get("id", "\0") in found.label_targets):
            names.append(attributes.get("name", attributes.get("type", "field")))
    return names


def _heading_findings(levels: list[int]) -> list[str]:
    findings = []
    if levels.count(1) != 1:
        findings.append(f"{levels.count(1)} h1 headings")
    previous = 0
    for level in levels:
        if previous and level > previous + 1:
            findings.append(f"heading jumps from h{previous} to h{level}")
        previous = level
    return findings


def _nameless(control: _Control) -> bool:
    if control.attributes.get("aria-label") or control.attributes.get("aria-labelledby"):
        return False
    return not control.text.strip() and control.attributes.get("title", "") == ""


def findings_of(html: str) -> list[str]:
    reader = _Reader()
    reader.feed(html)
    found = reader.found
    findings = [f"field without label: {name}" for name in _unlabelled_fields(found)]
    findings += ["image without text alternative"] * found.images_without_alternative
    duplicates = sorted({name for name in found.ids if found.ids.count(name) > 1})
    findings += [f"duplicate id: {name}" for name in duplicates]
    findings += _heading_findings(found.headings)
    nameless = [control for control in found.controls if _nameless(control)]
    findings += [f"{control.kind} without a name" for control in nameless]
    findings += [
        "table without header cells" for table in found.tables if not table.has_header_cell
    ]
    findings += [] if found.title.strip() else ["page without a title"]
    findings += ["title holds markup"] if found.title_markup else []
    if len(found.title.strip()) > TITLE_LIMIT:
        findings.append(f"title longer than {TITLE_LIMIT} characters")
    findings += ["cross-site token outside a form"] if found.token_outside_form else []
    findings += [] if found.has_lang else ["page without lang"]
    findings += [] if found.has_main else ["page without main"]
    return findings
