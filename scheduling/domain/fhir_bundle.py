"""Task 22, spec 15.1: a searchset Bundle with total and paging links."""

from collections.abc import Sequence
from urllib.parse import urlencode

from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_search import DEFAULT_COUNT, SearchQuery


def search_bundle(
    *,
    service_base: str,
    resource_type: str,
    query: SearchQuery,
    total: int,
    matches: Sequence[Resource],
    included: Sequence[Resource],
) -> Resource:
    entries = [_entry(service_base, item, "match") for item in matches]
    entries += [_entry(service_base, item, "include") for item in included]
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": total,
        "link": page_links(f"{service_base}/{resource_type}", query, total),
        "entry": entries,
    }


def page_links(address: str, query: SearchQuery, total: int) -> list[Resource]:
    links: list[Resource] = [{"relation": "self", "url": _address(address, query, query.offset)}]
    if query.count and query.offset + query.count < total:
        following = _address(address, query, query.offset + query.count)
        links.append({"relation": "next", "url": following})
    if query.offset > 0:
        previous = max(0, query.offset - max(query.count, DEFAULT_COUNT))
        links.append({"relation": "previous", "url": _address(address, query, previous)})
    return links


def _address(address: str, query: SearchQuery, offset: int) -> str:
    pairs = [(name, ",".join(found)) for name, found in query.filters]
    pairs += [("_count", str(query.count)), ("_offset", str(offset))]
    if query.sort:
        pairs.append(("_sort", f"-{query.sort}" if query.descending else query.sort))
    pairs += [("_include", item) for item in query.include]
    return f"{address}?{urlencode(pairs)}"


def _entry(service_base: str, resource: Resource, mode: str) -> Resource:
    return {
        "fullUrl": f"{service_base}/{resource['resourceType']}/{resource['id']}",
        "resource": resource,
        "search": {"mode": mode},
    }
