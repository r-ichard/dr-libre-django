"""Task 10a: the root path is the public search, a plain GET form over the search use case."""

from django.http import HttpRequest, HttpResponse

from scheduling.domain.search_address import parse_list_kind
from scheduling.domain.search_query import parse_search_query
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.search import search_public
from scheduling.use_cases.search_filter_options import load_filter_options
from scheduling.views.pages.page_view import PageView
from scheduling.views.pages.search_context import search_context


class SearchPage(PageView):
    template_name = "search/index.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        kind = parse_list_kind(request.GET.get("list", ""))
        query = parse_search_query(request.GET.dict())
        found = search_public(kind, query, current_request_context().now)
        return self.page(request, search_context(kind, query, found, load_filter_options()))
