"""The /api/v1 access table (spec §14) lists every route, and no row names a gone route."""

from collections.abc import Iterator

from django.urls import URLPattern, URLResolver, get_resolver

from scheduling.views.test_api_access_rows import ANY_METHOD, API_ACCESS_ROWS

API_PREFIXES = ("api/v1/", "^api/v1/")
HANDLER_METHODS = ("get", "post", "put", "patch", "delete")
RouteKey = tuple[str, str]


def _routes(
    patterns: list[URLPattern | URLResolver], prefix: str = ""
) -> Iterator[tuple[str, URLPattern]]:
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _routes(list(pattern.url_patterns), route)
        else:
            yield route, pattern


def _walked_keys() -> set[RouteKey]:
    keys: set[RouteKey] = set()
    for route, pattern in _routes(list(get_resolver().url_patterns)):
        if not route.startswith(API_PREFIXES):
            continue
        view_class = getattr(pattern.callback, "cls", object)
        methods = [method.upper() for method in HANDLER_METHODS if hasattr(view_class, method)]
        keys.update((method, route) for method in methods or [ANY_METHOD])
    return keys


def _table_keys() -> set[RouteKey]:
    return {(row.method, row.route) for row in API_ACCESS_ROWS}


def returns_no_route_unlisted_when_the_url_configuration_is_walked() -> None:
    walked = _walked_keys()
    assert walked
    unlisted = sorted(walked - _table_keys())

    assert unlisted == []


def returns_no_row_for_a_removed_route_when_the_table_is_compared() -> None:
    removed = sorted(_table_keys() - _walked_keys())

    assert removed == []
