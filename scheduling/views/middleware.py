import logging
import time
import uuid
from collections.abc import Callable

from django.core.exceptions import RequestDataTooBig, TooManyFieldsSent
from django.core.signals import got_request_exception
from django.dispatch import receiver
from django.http import HttpRequest, HttpResponse

from scheduling.domain.request_context import RequestContext, is_sane_correlation_id
from scheduling.use_cases.request_context import bind_request_context
from scheduling.views import clock
from scheduling.views.failure_response import (
    INTERNAL_ERROR_CODE,
    INTERNAL_ERROR_MESSAGE,
    INTERNAL_ERROR_STATUS,
    error_response,
)
from scheduling.views.fhir.responses import internal_error_response
from scheduling.views.pages.errors import bad_request_page

CORRELATION_HEADER = "X-Correlation-Id"
UNMATCHED_ROUTE = "<unmatched>"
API_PREFIX = "/api/v1/"
FHIR_PREFIX = "/fhir"

request_logger = logging.getLogger("drlibre.request")
error_logger = logging.getLogger("drlibre.error")


@receiver(got_request_exception)
def log_unexpected_error(**_: object) -> None:
    """Django sends this for any error no view handled, inside the request context."""
    error_logger.error("unexpected error", exc_info=True)


def generic_api_error() -> HttpResponse:
    response: HttpResponse = error_response(
        INTERNAL_ERROR_CODE, INTERNAL_ERROR_STATUS, INTERNAL_ERROR_MESSAGE, {}
    ).render()
    return response


def is_fhir_path(path: str) -> bool:
    return path == FHIR_PREFIX or path.startswith(f"{FHIR_PREFIX}/")


class RequestContextMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        offered = request.headers.get(CORRELATION_HEADER, "")
        correlation_id = offered if is_sane_correlation_id(offered) else uuid.uuid4().hex
        context = RequestContext(correlation_id=correlation_id, now=clock.now_utc())
        started = time.perf_counter()
        with bind_request_context(context):
            response = self.get_response(request)
            is_api = request.path.startswith(API_PREFIX)
            if is_api and response.status_code == INTERNAL_ERROR_STATUS:
                response = generic_api_error()
            elif is_fhir_path(request.path) and response.status_code == INTERNAL_ERROR_STATUS:
                response = internal_error_response()
            response[CORRELATION_HEADER] = correlation_id
            match = request.resolver_match
            request_logger.info(
                "request",
                extra={
                    "method": request.method,
                    "route": match.route if match and match.route else UNMATCHED_ROUTE,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )
        return response

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        """With DEBUG on Django would show its technical page for a refused size; pages get ours."""
        if request.path.startswith(API_PREFIX) or is_fhir_path(request.path):
            return None
        if isinstance(exception, TooManyFieldsSent | RequestDataTooBig):
            return bad_request_page(request, exception)
        return None
