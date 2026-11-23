"""The root path: the public search, a plain GET form over the search use case."""

from django.http import HttpRequest, HttpResponse

from scheduling.domain.failure import Failure
from scheduling.domain.rate_limit_rules import WINDOW, wait_sentence
from scheduling.domain.search_address import parse_list_kind
from scheduling.domain.search_query import SearchQuery, parse_search_query
from scheduling.use_cases.search_filter_options import FilterOptions, load_filter_options
from scheduling.use_cases.search_limited import search_for_visitor
from scheduling.use_cases.search_types import AnyResult
from scheduling.use_cases.search_types import SearchPage as SearchResults
from scheduling.views.network_address import network_address
from scheduling.views.pages.page_view import PageView, render_page
from scheduling.views.pages.search_context import search_context

WINDOW_SECONDS = int(WINDOW.total_seconds())


class SearchPage(PageView):
    template_name = "search/index.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        kind = parse_list_kind(request.GET.get("list", ""))
        query = parse_search_query(request.GET.dict())
        found = search_for_visitor(kind, query, network_address(request), self.user)
        options = load_filter_options()
        if isinstance(found, Failure):
            return self._limited(request, kind, query, options, found)
        return self.page(request, search_context(kind, query, found.value, options))

    def _limited(
        self,
        request: HttpRequest,
        kind: str,
        query: SearchQuery,
        options: FilterOptions,
        found: Failure,
    ) -> HttpResponse:
        """The search page itself with the message where the results would be: every other link on
        it must answer for a limited visitor, so the result links and list switch are left out."""
        wait = found.retry_after_seconds or WINDOW_SECONDS
        empty: SearchResults[AnyResult] = SearchResults([], 0, 1, 1, query.page_size)
        context = {
            **search_context(kind, query, empty, options),
            "limited_message": f"This network address searched too often. {wait_sentence(wait)}",
        }
        response = render_page(
            request, self.template_name, context, status=429, signed_in_user=self.user
        )
        response["Retry-After"] = str(wait)
        return response
