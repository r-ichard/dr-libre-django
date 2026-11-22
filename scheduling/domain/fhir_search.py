"""Task 22, spec 15.5: read a FHIR search against the declaration. Anything not declared, repeated
or unreadable is refused and named, so a search never returns more than was asked for."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_common import carries_only_storable_text
from scheduling.domain.fhir_dates import normalised_date
from scheduling.domain.fhir_declaration import (
    COMMON_PARAMETERS,
    ParameterKind,
    ResourceDeclaration,
    SearchParameter,
)
from scheduling.domain.fhir_near import parse_near
from scheduling.domain.request_limits import MAXIMUM_FIELDS, MAXIMUM_PAGE

DEFAULT_COUNT = 20
MAXIMUM_COUNT = 100
MAXIMUM_TEXT = 100
DEFAULT_SORT = "name"
_WHOLE_VALUE_KINDS = (ParameterKind.DATE, ParameterKind.NEAR)
SERVED_FORMATS = ("json", "application/fhir+json")


@dataclass(frozen=True)
class SearchQuery:
    filters: tuple[tuple[str, tuple[str, ...]], ...]
    count: int
    offset: int
    sort: str
    descending: bool
    include: tuple[str, ...]


def parse_search(
    declaration: ResourceDeclaration, params: Mapping[str, Sequence[str]]
) -> Result[SearchQuery]:
    filters: list[tuple[str, tuple[str, ...]]] = []
    count, offset = DEFAULT_COUNT, 0
    sort = DEFAULT_SORT if DEFAULT_SORT in declaration.sortable else ""
    include: list[str] = []
    for name, values in params.items():
        if not values or len(values) > _repeats_allowed(declaration, name):
            return _refuse(name, "A parameter may be given once.")
        value = values[0]
        if not all(carries_only_storable_text(item) for item in (name, *values)):
            return _refuse(name, "The value cannot be read.")
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
            include = [item for item in declaration.includes if item in values]
            problem = any(item not in declaration.includes for item in values)
        else:
            parameter = declaration.parameter(name)
            if parameter is None or name in COMMON_PARAMETERS:
                return _refuse(name, "This search parameter is not supported.")
            problem = False
            for item in values:
                alternatives = _read_value(parameter, item)
                if isinstance(alternatives, Failure):
                    return alternatives
                filters.append((name, alternatives))
        if problem:
            return _refuse(name, "The value cannot be read.")
    missing = _missing_required(declaration, filters)
    if missing is not None:
        return _refuse(missing, "This search parameter is required.")
    descending = params.get("_sort", [""])[0].startswith("-")
    return Success(SearchQuery(tuple(filters), count, offset, sort, descending, tuple(include)))


def _repeats_allowed(declaration: ResourceDeclaration, name: str) -> int:
    """`_include` repeats freely; any other parameter repeats as often as it is declared."""
    parameter = declaration.parameter(name)
    if name == "_include":
        return MAXIMUM_FIELDS
    return parameter.maximum_repeats if parameter is not None else 1


def _missing_required(
    declaration: ResourceDeclaration, filters: list[tuple[str, tuple[str, ...]]]
) -> str | None:
    given = {name for name, _ in filters}
    return next(
        (item.name for item in declaration.parameters if item.required and item.name not in given),
        None,
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


def _read_value(parameter: SearchParameter, value: str) -> tuple[str, ...] | Failure:
    """The alternatives a value names ("either", comma-separated), or the refusal naming it."""
    kind = parameter.kind
    pieces = [value] if kind in _WHOLE_VALUE_KINDS else value.split(",")
    read = [_read_piece(kind, piece) for piece in pieces]
    if None in read:
        return _refuse(parameter.name, "The value cannot be read.")
    alternatives = tuple(item for item in read if item is not None)
    unknown = [item for item in alternatives if parameter.codes and item not in parameter.codes]
    if unknown:
        return _refuse(parameter.name, f"Use one of: {', '.join(parameter.codes)}.")
    return alternatives


def _read_piece(kind: ParameterKind, value: str) -> str | None:
    if kind is ParameterKind.FLAG:
        return value if value in ("true", "false") else None
    if kind is ParameterKind.REFERENCE:
        return parse_id(value.rsplit("/", 1)[-1])
    if kind is ParameterKind.DATE:
        return normalised_date(value)
    if kind is ParameterKind.NEAR:
        return value if parse_near(value) is not None else None
    code = (value if kind is ParameterKind.TEXT else value.rsplit("|", 1)[-1]).strip()
    return code if 0 < len(code) <= MAXIMUM_TEXT else None


def _refuse(name: str, message: str) -> Failure:
    return Failure.invalid_input([FieldMessage(name, message)])
