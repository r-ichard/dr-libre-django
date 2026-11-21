"""Section 14: GET /search/providers, /search/hospitals, /search/specialties. Public, so no
identity is read."""

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.search_query import parse_search_query
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.search import search_public
from scheduling.views.access import public
from scheduling.views.api_view import ApiView
from scheduling.views.search_schemas import search_body


class SearchView(ApiView):
    permission_classes = public()
    kind = ""

    def get(self, request: Request) -> Response:
        query = parse_search_query(request.query_params)
        return Response(search_body(search_public(self.kind, query, current_request_context().now)))


class SearchProvidersView(SearchView):
    kind = "providers"


class SearchHospitalsView(SearchView):
    kind = "hospitals"


class SearchSpecialtiesView(SearchView):
    kind = "specialties"
