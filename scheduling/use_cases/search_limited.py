"""Section 7.5 for the public search: one network address may run 120 searches an hour."""

from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.rate_limit_rules import RateLimitScope
from scheduling.domain.search_query import SearchQuery
from scheduling.use_cases.rate_limits import take_hit
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.search import search_public
from scheduling.use_cases.search_types import AnyResult, SearchPage


def search_for_visitor(
    kind: str, query: SearchQuery, address: str
) -> Result[SearchPage[AnyResult]]:
    wait = take_hit(RateLimitScope.SEARCH, None, address)
    if wait is not None:
        return Failure.rate_limited(wait)
    return Success(search_public(kind, query, current_request_context().now))
