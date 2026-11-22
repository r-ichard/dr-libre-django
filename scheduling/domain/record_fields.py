"""Sections 3.1 and 10: what the admin forms check beyond a column's type. Each check takes what
a browser sent as text and returns the value to store, or the field's message."""

import math
from collections.abc import Collection

from scheduling.domain.failure import Failure, FieldMessage, Result, Success

NAME_LENGTH = 200
CODE_LENGTH = 50
LARGEST_STORED_NUMBER = 32767
COLOUR_DIGITS = frozenset("0123456789abcdef")
COLOUR_LENGTH = 7
EQUIPMENT_LENGTH = 100
NULL_MESSAGE = "Remove the character that cannot be saved."


def _refused(field: str, message: str) -> Failure:
    return Failure.invalid_input([FieldMessage(field, message)])


def clean_code(raw: str) -> str:
    return raw.strip().lower()


def check_text(field: str, raw: str, maximum: int, blank_message: str | None) -> Result[str]:
    """`blank_message` None means the field may be empty."""
    text = raw.strip()
    if "\x00" in text:
        return _refused(field, NULL_MESSAGE)
    if not text and blank_message is not None:
        return _refused(field, blank_message)
    if len(text) > maximum:
        return _refused(field, f"Use at most {maximum} characters.")
    return Success(text)


def check_name(raw: str) -> Result[str]:
    return check_text("name", raw, NAME_LENGTH, "Enter a name.")


def check_code(raw: str) -> Result[str]:
    return check_text("code", clean_code(raw), CODE_LENGTH, "Enter a code.")


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


def _whole_number(field: str, raw: str, minimum: int) -> Result[int]:
    message = f"Use a whole number of {minimum} or more."
    try:
        number = int(raw.strip())
    except ValueError:
        return _refused(field, message)
    if number < minimum:
        return _refused(field, message)
    if number > LARGEST_STORED_NUMBER:
        return _refused(field, f"Use a whole number of at most {LARGEST_STORED_NUMBER}.")
    return Success(number)


def check_capacity(raw: str) -> Result[int]:
    return _whole_number("capacity", raw, 1)


def check_duration_minutes(raw: str) -> Result[int]:
    return _whole_number("duration_minutes", raw, 1)


def check_buffer_minutes(raw: str) -> Result[int]:
    return _whole_number("buffer_minutes", raw, 0)


def check_equipment(raw: str) -> Result[list[str]]:
    """One item per line; blank lines are dropped."""
    if "\x00" in raw:
        return _refused("equipment", NULL_MESSAGE)
    items = [line.strip() for line in raw.splitlines() if line.strip()]
    if any(len(item) > EQUIPMENT_LENGTH for item in items):
        return _refused("equipment", f"Use at most {EQUIPMENT_LENGTH} characters on a line.")
    return Success(items)
