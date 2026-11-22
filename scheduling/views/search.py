"""Section 14: GET /search/providers, /search/hospitals, /search/specialties. Public, so no
identity is read."""

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure
from scheduling.domain.search_query import parse_search_query
from scheduling.use_cases.search_limited import search_for_visitor
from scheduling.views.access import public
from scheduling.views.api_view import ApiView
from scheduling.views.failure_response import failure_response
from scheduling.views.network_address import network_address
from scheduling.views.search_schemas import search_body


class SearchView(ApiView):
    permission_classes = public()
    kind = ""

    def get(self, request: Request) -> Response:
        query = parse_search_query(request.query_params)
        found = search_for_visitor(self.kind, query, network_address(request))
        if isinstance(found, Failure):
            return failure_response(found)
        return Response(search_body(found.value))


class SearchProvidersView(SearchView):
    kind = "providers"


class SearchHospitalsView(SearchView):
    kind = "hospitals"


class SearchSpecialtiesView(SearchView):
    kind = "specialties"
