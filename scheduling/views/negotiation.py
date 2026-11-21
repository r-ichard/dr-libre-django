from collections.abc import Iterable

from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.parsers import BaseParser
from rest_framework.renderers import BaseRenderer
from rest_framework.request import Request


class AlwaysJsonNegotiation(BaseContentNegotiation):
    """Every API answer is JSON whatever Accept says, so 406 cannot occur."""

    def select_parser(self, request: Request, parsers: Iterable[BaseParser]) -> BaseParser | None:
        return next(iter(parsers), None)

    def select_renderer(
        self, request: Request, renderers: Iterable[BaseRenderer], format_suffix: str | None = None
    ) -> tuple[BaseRenderer, str]:
        renderer = next(iter(renderers))
        return renderer, renderer.media_type
