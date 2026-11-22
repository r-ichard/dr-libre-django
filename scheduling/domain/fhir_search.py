"""Task 22, spec 15.5: read a FHIR search against the declaration. Anything not declared, repeated
or unreadable is refused and named, so a search never returns more than was asked for."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_declaration import (
    COMMON_PARAMETERS,
    ParameterKind,
    ResourceDeclaration,
)
from scheduling.domain.fhir_near import parse_near
from scheduling.domain.request_limits import MAXIMUM_PAGE

DEFAULT_COUNT = 20
MAXIMUM_COUNT = 100
MAXIMUM_TEXT = 100
SERVED_FORMATS = ("json", "application/fhir+json")


@dataclass(frozen=True)
class SearchQuery:
    filters: tuple[tuple[str, str], ...]
    count: int
    offset: int
    sort: str
    descending: bool
    include: tuple[str, ...]


def parse_search(
    declaration: ResourceDeclaration, params: Mapping[str, Sequence[str]]
) -> Result[SearchQuery]:
    filters: list[tuple[str, str]] = []
    count, offset, sort, include = DEFAULT_COUNT, 0, "name", ""
    for name, values in params.items():
        if len(values) != 1:
            return _refuse(name, "A parameter may be given once.")
        value = values[0]
        if name == "_count":
            count = _number(value, 0, MAXIMUM_COUNT)
            problem = count < 0
        elif name == "_offset":
            offset = _number(value, 0, MAXIMUM_PAGE)
            problem = offset < 0
        elif name == "_sort":
            sort = value.removeprefix("-")
            problem = sort not in declaration.sortable
        elif name == "_format":
            problem = value not in SERVED_FORMATS
        elif name == "_include":
            include = value
            problem = value not in declaration.includes
        else:
            parameter = declaration.parameter(name)
            if parameter is None or name in COMMON_PARAMETERS:
                return _refuse(name, "This search parameter is not supported.")
            normalised = _read_value(parameter.kind, value)
            problem = normalised is None
            filters.append((name, normalised or ""))
        if problem:
            return _refuse(name, "The value cannot be read.")
    descending = params.get("_sort", [""])[0].startswith("-")
    return Success(
        SearchQuery(tuple(filters), count, offset, sort, descending, (include,) if include else ())
    )


def parse_id(text: str) -> str | None:
    """The canonical form of a resource id, or None when it is not one."""
    try:
        return str(UUID(text)) if len(text) <= 36 else None
    except ValueError:
        return None


def _number(text: str, low: int, high: int) -> int:
    if text.isascii() and text.isdigit() and low <= int(text) <= high:
        return int(text)
    return -1


def _read_value(kind: ParameterKind, value: str) -> str | None:
    if kind is ParameterKind.FLAG:
        return value if value in ("true", "false") else None
    if kind is ParameterKind.REFERENCE:
        return parse_id(value.rsplit("/", 1)[-1])
    if kind is ParameterKind.NEAR:
        return value if parse_near(value) is not None else None
    code = (value if kind is ParameterKind.TEXT else value.rsplit("|", 1)[-1]).strip()
    return code if 0 < len(code) <= MAXIMUM_TEXT else None


def _refuse(name: str, message: str) -> Failure:
    return Failure.invalid_input([FieldMessage(name, message)])
