from collections.abc import Iterable

from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.parsers import BaseParser
from rest_framework.renderers import BaseRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class AlwaysJsonNegotiation(BaseContentNegotiation):
    """Liveness probes and browsers must get JSON whatever Accept says."""

    def select_parser(self, request: Request, parsers: Iterable[BaseParser]) -> BaseParser | None:
        return next(iter(parsers), None)

    def select_renderer(
        self, request: Request, renderers: Iterable[BaseRenderer], format_suffix: str | None = None
    ) -> tuple[BaseRenderer, str]:
        renderer = next(iter(renderers))
        return renderer, renderer.media_type


class HealthView(APIView):
    content_negotiation_class = AlwaysJsonNegotiation

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})
