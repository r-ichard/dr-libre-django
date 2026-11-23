"""The hit an API read takes before it computes anything."""

from rest_framework.request import Request

from scheduling.domain.failure import Failure
from scheduling.domain.rate_limit_rules import RateLimitScope
from scheduling.models import User
from scheduling.use_cases.read_limits import take_read_hit
from scheduling.views.network_address import network_address


def signed_in(request: Request) -> User | None:
    return request.user if isinstance(request.user, User) else None


def api_read_refusal(request: Request) -> Failure | None:
    """Schedule reads of the API share one counter with the pages."""
    wait = take_read_hit(RateLimitScope.SCHEDULE, signed_in(request), network_address(request))
    return None if wait is None else Failure.rate_limited(wait)
