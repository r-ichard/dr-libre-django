"""Section 14: GET /providers/{id}, /hospitals/{id}, /specialties/{id}. Public, so no identity is
read."""

from uuid import UUID

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure
from scheduling.use_cases.public_details import (
    load_hospital_detail,
    load_provider_detail,
    load_specialty_detail,
)
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.access import public
from scheduling.views.api_view import ApiView
from scheduling.views.detail_schemas import hospital_detail_body, provider_detail_body
from scheduling.views.failure_response import failure_response
from scheduling.views.search_schemas import specialty_body


class ProviderDetailView(ApiView):
    permission_classes = public()

    def get(self, request: Request, provider_id: UUID) -> Response:
        loaded = load_provider_detail(provider_id, None, current_request_context().now)
        if isinstance(loaded, Failure):
            return failure_response(loaded)
        return Response(provider_detail_body(loaded.value))


class HospitalDetailView(ApiView):
    permission_classes = public()

    def get(self, request: Request, hospital_id: UUID) -> Response:
        loaded = load_hospital_detail(hospital_id, current_request_context().now)
        if isinstance(loaded, Failure):
            return failure_response(loaded)
        return Response(hospital_detail_body(loaded.value))


class SpecialtyDetailView(ApiView):
    permission_classes = public()

    def get(self, request: Request, specialty_id: UUID) -> Response:
        loaded = load_specialty_detail(specialty_id, 1, current_request_context().now)
        if isinstance(loaded, Failure):
            return failure_response(loaded)
        return Response(specialty_body(loaded.value.specialty))
