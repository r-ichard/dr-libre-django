from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from scheduling.domain.request_context import RequestContext

_current_context: ContextVar[RequestContext] = ContextVar("request_context")


def current_request_context() -> RequestContext:
    """Raises LookupError outside a request: reading without a binding is a broken invariant."""
    return _current_context.get()


@contextmanager
def bind_request_context(context: RequestContext) -> Iterator[None]:
    token = _current_context.set(context)
    try:
        yield
    finally:
        _current_context.reset(token)
