"""Section 13: the dates a dashboard range covers, and which date counts as today."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_RANGE_DAYS = 7
RANGE_DAYS = {"today": 1, "7": 7, "30": 30}


def report_days(raw_range: str, today: date) -> list[date]:
    count = RANGE_DAYS.get(raw_range, DEFAULT_RANGE_DAYS)
    return [today - timedelta(days=offset) for offset in reversed(range(count))]


def current_report_date(now: datetime, hospital_zones: list[str]) -> date:
    """Latest current date at any hospital; hospitals share one dashboard, so one "today"."""
    zones = hospital_zones or ["UTC"]
    return max(now.astimezone(ZoneInfo(zone)).date() for zone in zones)
