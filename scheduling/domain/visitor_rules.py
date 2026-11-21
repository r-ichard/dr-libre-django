"""Section 7.1 step 3: what a visitor may type about themselves."""

from datetime import date

MAXIMUM_AGE_YEARS = 120


def valid_birth_date(birth_date: date, today: date) -> bool:
    """Not in the future and not more than 120 years back. Compared as year, month, day so that a
    29 February today needs no date 120 years ago."""
    oldest = (today.year - MAXIMUM_AGE_YEARS, today.month, today.day)
    return (birth_date.year, birth_date.month, birth_date.day) >= oldest and birth_date <= today


def normalise_email(address: str) -> str:
    return address.strip().lower()
