"""Task 11, section 6.6: provider, hospital and specialty pages. Open to everyone; an id search
would not list answers not found."""

from uuid import UUID

from django.http import Http404, HttpRequest, HttpResponse

from scheduling.domain.failure import Failure
from scheduling.domain.search_query import parse_search_query
from scheduling.use_cases.booking_page_data import week_of_slots
from scheduling.use_cases.public_details import (
    load_hospital_detail,
    load_provider_detail,
    load_specialty_detail,
)
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.booking_links import path_uuid, week_from
from scheduling.views.pages.detail_context import (
    hospital_context,
    provider_context,
    specialty_context,
)
from scheduling.views.pages.page_view import PageView


class ProviderPage(PageView):
    template_name = "details/provider.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        provider_id = path_uuid(self, "provider_id")
        asked_type = _uuid_or_none(request.GET.get("type", ""))
        loaded = load_provider_detail(provider_id, asked_type, current_request_context().now)
        if isinstance(loaded, Failure):
            raise Http404
        detail = loaded.value
        week = week_of_slots(
            detail.chosen_type.id, provider_id, week_from(request.GET.get("week", ""))
        )
        if isinstance(week, Failure):
            raise Http404
        return self.page(request, provider_context(detail, week.value))


class HospitalPage(PageView):
    template_name = "details/hospital.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        hospital_id = path_uuid(self, "hospital_id")
        loaded = load_hospital_detail(hospital_id, current_request_context().now)
        if isinstance(loaded, Failure):
            raise Http404
        return self.page(request, hospital_context(loaded.value))


class SpecialtyPage(PageView):
    template_name = "details/specialty.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        specialty_id = path_uuid(self, "specialty_id")
        paging = parse_search_query(
            {key: request.GET.get(key, "") for key in ("page", "page_size")}
        )
        loaded = load_specialty_detail(
            specialty_id, paging.page, current_request_context().now, paging.page_size
        )
        if isinstance(loaded, Failure):
            raise Http404
        return self.page(request, specialty_context(loaded.value, paging))


def _uuid_or_none(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except ValueError:
        return None
