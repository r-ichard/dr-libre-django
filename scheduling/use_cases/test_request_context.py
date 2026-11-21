from datetime import UTC, datetime

import pytest

from scheduling.domain.request_context import RequestContext
from scheduling.use_cases.request_context import bind_request_context, current_request_context

FIXED_INSTANT = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)


def returns_bound_context_when_read_inside_bind() -> None:
    context = RequestContext(correlation_id="abc", now=FIXED_INSTANT)

    with bind_request_context(context):
        assert current_request_context() == context


def raises_when_context_is_read_outside_a_request() -> None:
    with pytest.raises(LookupError):
        current_request_context()


def raises_when_context_is_read_after_bind_has_ended() -> None:
    with bind_request_context(RequestContext(correlation_id="abc", now=FIXED_INSTANT)):
        pass

    with pytest.raises(LookupError):
        current_request_context()
