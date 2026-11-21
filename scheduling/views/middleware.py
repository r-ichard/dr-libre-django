import logging
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from scheduling.domain.request_context import RequestContext, is_sane_correlation_id
from scheduling.use_cases.request_context import bind_request_context
from scheduling.views import clock

CORRELATION_HEADER = "X-Correlation-Id"
UNMATCHED_ROUTE = "<unmatched>"

request_logger = logging.getLogger("drlibre.request")


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
