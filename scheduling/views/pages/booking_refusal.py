"""Section 7.1: a refused booking step as a page with the reason and a way forward."""

from dataclasses import dataclass
from uuid import UUID

from django.http import HttpRequest, HttpResponse

from scheduling.domain.booking_refusals import Refusal, refusal_for
from scheduling.domain.failure import Failure
from scheduling.models import User
from scheduling.views.pages.booking_links import START_PATH, times_href
from scheduling.views.pages.page_view import render_page

REFUSED_TEMPLATE = "booking/refused.html"


@dataclass(frozen=True)
class WayBack:
    """Where each kind of refusal sends the reader."""

    type_id: UUID | None = None
    provider_id: UUID | None = None
    retry_href: str = START_PATH


def refused_page(
    request: HttpRequest, failure: Failure, way_back: WayBack, signed_in_user: User | None
) -> HttpResponse:
    refusal = refusal_for(failure)
    href, text = _way_forward(refusal, way_back)
    context = {"message": refusal.message, "action_href": href, "action_text": text}
    return render_page(
        request, REFUSED_TEMPLATE, context, status=refusal.status, signed_in_user=signed_in_user
    )


def _way_forward(refusal: Refusal, way_back: WayBack) -> tuple[str, str]:
    if refusal.way_forward == "times" and way_back.type_id is not None:
        return times_href(way_back.type_id, way_back.provider_id), "See the refreshed times"
    if refusal.way_forward == "retry":
        return way_back.retry_href, "Try again"
    return START_PATH, "Start again"
