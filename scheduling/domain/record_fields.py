"""Sections 3.1 and 10: what the admin forms check beyond a column's type. Each check takes what
a browser sent as text and returns the value to store, or the field's message."""

import math
from collections.abc import Collection

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.text_rules import check_storable_text
from scheduling.domain.whole_numbers import SMALLINT_MAXIMUM, check_whole_number

NAME_LENGTH = 200
CODE_LENGTH = 50
COLOUR_DIGITS = frozenset("0123456789abcdef")
COLOUR_LENGTH = 7
EQUIPMENT_LENGTH = 100


def _refused(field: str, message: str) -> Failure:
    return Failure.invalid_input([FieldMessage(field, message)])


def clean_code(raw: str) -> str:
    return raw.strip().lower()


def check_text(
    field: str,
    raw: str,
    maximum: int,
    blank_message: str | None,
    *,
    single_line: bool,
) -> Result[str]:
    """`blank_message` None means the field may be empty. The caller says whether the field
    is one line: the page reads it from the field's widget, the API from its schema."""
    text = raw.strip()
    unstorable = check_storable_text(field, text, single_line=single_line)
    if isinstance(unstorable, Failure):
        return unstorable
    if not text and blank_message is not None:
        return _refused(field, blank_message)
    if len(text) > maximum:
        return _refused(field, f"Use at most {maximum} characters.")
    return Success(text)


def check_name(raw: str) -> Result[str]:
    return check_text("name", raw, NAME_LENGTH, "Enter a name.", single_line=True)


def check_code(raw: str) -> Result[str]:
    return check_text("code", clean_code(raw), CODE_LENGTH, "Enter a code.", single_line=True)


def check_colour(raw: str) -> Result[str]:
    colour = raw.strip().lower()
    is_hex = colour[:1] == "#" and all(digit in COLOUR_DIGITS for digit in colour[1:])
    if len(colour) != COLOUR_LENGTH or not is_hex:
        return _refused("colour", "Use a colour like #1a2b3c.")
    return Success(colour)


def _degrees(field: str, raw: str, limit: int) -> Result[float]:
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or abs(value) > limit:
        return _refused(field, f"Use a number from -{limit} to {limit}.")
    return Success(value)


def check_coordinates(
    raw_latitude: str, raw_longitude: str
) -> Result[tuple[float | None, float | None]]:
    latitude_text, longitude_text = raw_latitude.strip(), raw_longitude.strip()
    if not latitude_text and not longitude_text:
        return Success((None, None))
    if not longitude_text:
        return _refused("longitude", "Give longitude too, or clear latitude.")
    if not latitude_text:
        return _refused("latitude", "Give latitude too, or clear longitude.")
    latitude = _degrees("latitude", latitude_text, 90)
    if isinstance(latitude, Failure):
        return latitude
    longitude = _degrees("longitude", longitude_text, 180)
    if isinstance(longitude, Failure):
        return longitude
    return Success((latitude.value, longitude.value))


def check_time_zone(raw: str, known_zones: Collection[str]) -> Result[str]:
    zone = raw.strip()
    if zone not in known_zones:
        return _refused("time_zone", "Choose a time zone from the list.")
    return Success(zone)


def check_capacity(raw: str) -> Result[int]:
    return check_whole_number("capacity", raw, 1, SMALLINT_MAXIMUM)


def check_duration_minutes(raw: str) -> Result[int]:
    return check_whole_number("duration_minutes", raw, 1, SMALLINT_MAXIMUM)


def check_buffer_minutes(raw: str) -> Result[int]:
    return check_whole_number("buffer_minutes", raw, 0, SMALLINT_MAXIMUM)


def check_equipment(raw: str) -> Result[list[str]]:
    """One item per line; blank lines are dropped."""
    unstorable = check_storable_text("equipment", raw, single_line=False)
    if isinstance(unstorable, Failure):
        return unstorable
    items = [line.strip() for line in raw.splitlines() if line.strip()]
    if any(len(item) > EQUIPMENT_LENGTH for item in items):
        return _refused("equipment", f"Use at most {EQUIPMENT_LENGTH} characters on a line.")
    return Success(items)
