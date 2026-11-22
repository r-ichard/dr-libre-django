"""Section 7.1 step 3: what a visitor may type about themselves."""

import re
from datetime import date

from scheduling.domain.audit_metadata import HOSTNAME_PATTERN

MAXIMUM_AGE_YEARS = 120
EMAIL_MAXIMUM = 254
LOCAL_PART_PATTERN = re.compile(r"[^@\s]+")


def valid_birth_date(birth_date: date, today: date) -> bool:
    """Not in the future and not more than 120 years back. Compared as year, month, day so that a
    29 February today needs no date 120 years ago."""
    oldest = (today.year - MAXIMUM_AGE_YEARS, today.month, today.day)
    return (birth_date.year, birth_date.month, birth_date.day) >= oldest and birth_date <= today


def normalise_email(address: str) -> str:
    return address.strip().lower()


def is_valid_email(address: str) -> bool:
    """The one email rule: a free-form local part, one at sign, a dotted host name."""
    local, separator, host = address.partition("@")
    return (
        len(address) <= EMAIL_MAXIMUM
        and bool(separator)
        and LOCAL_PART_PATTERN.fullmatch(local) is not None
        and HOSTNAME_PATTERN.fullmatch(host) is not None
    )
