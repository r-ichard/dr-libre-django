"""Task 27a: a day as a person reads it."""

from datetime import date


def day_label(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B %Y}"
