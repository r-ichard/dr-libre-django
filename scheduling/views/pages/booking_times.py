"""Task 12a, times: a week of free slots in the hospital's zone."""

from collections.abc import Callable
from datetime import date, datetime, timedelta

from django.http import Http404, HttpRequest, HttpResponse

from scheduling.domain.booking_week import next_week_start, previous_week_start
from scheduling.domain.failure import Failure
from scheduling.use_cases.booking_page_data import WeekOfSlots, week_of_slots
from scheduling.views.pages.booking_links import (
    clock_label,
    day_label,
    details_href,
    path_uuid,
    provider_from,
    times_href,
    week_from,
)
from scheduling.views.pages.booking_summary import slot_summary
from scheduling.views.pages.page_view import PageView

DAYS_PER_WEEK = 7


class TimesPage(PageView):
    template_name = "booking/times.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        type_id = path_uuid(self, "appointment_type_id")
        provider_id = provider_from(request.GET.get("provider", ""))
        loaded = week_of_slots(type_id, provider_id, week_from(request.GET.get("week", "")))
        if isinstance(loaded, Failure):
            raise Http404
        week = loaded.value

        def week_href(week_start: date) -> str:
            return times_href(type_id, provider_id, week_start)

        context = {"summary": slot_summary(week.choice, None), **week_strip(week, week_href)}
        return self.page(request, context)


def week_strip(
    week: WeekOfSlots,
    week_href: Callable[[date], str],
    slot_href: Callable[[datetime], str] | None = None,
) -> dict[str, object]:
    """The context of components/week_strip.html, for every page that shows a week of slots."""
    type_id = week.choice.appointment_type.pk
    clinician = week.choice.clinician
    provider_id = clinician.pk if clinician else None
    days = []
    for offset in range(DAYS_PER_WEEK):
        day = week.week_start + timedelta(days=offset)
        heading = f"{day:%a} {day.day} {day:%b}"
        spoken_day = day_label(day)
        slots = [
            {
                "label": clock_label(start, week.time_zone),
                "href": slot_href(start)
                if slot_href
                else details_href(type_id, provider_id, start),
                "day": spoken_day,
            }
            for start in week.days.get(day, [])
        ]
        days.append({"heading": heading, "slots": slots})
    last_day = week.week_start + timedelta(days=DAYS_PER_WEEK - 1)
    return {
        "days": days,
        "has_slots": bool(week.days),
        "week_label": f"{day_label(week.week_start)} to {day_label(last_day)}",
        "previous_href": week_href(previous_week_start(week.week_start)),
        "next_href": week_href(next_week_start(week.week_start)),
    }
