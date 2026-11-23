"""Sections 3.1 and 10: the checks of the admin forms that a column cannot say."""

import pytest

from scheduling.domain.failure import Failure, FailureCode, FieldMessage, Success


def _call(name: str, *arguments: object) -> object:
    from scheduling.domain import record_fields

    return getattr(record_fields, name)(*arguments)


KNOWN_ZONES = frozenset({"Europe/Paris", "UTC"})


def _failed(field: str, message: str) -> Failure:
    return Failure.invalid_input([FieldMessage(field, message)])


def returns_code_in_lower_case_without_outer_spaces_when_typed_with_capitals() -> None:
    assert _call("clean_code", "  Cardio-1 ") == "cardio-1"


def returns_stored_code_when_code_has_capitals_and_outer_spaces() -> None:
    assert _call("check_code", "  Cardio-1 ") == Success("cardio-1")


def returns_error_when_code_is_blank_after_trim() -> None:
    assert _call("check_code", "   ") == _failed("code", "Enter a code.")


def returns_code_when_it_has_50_characters() -> None:
    assert _call("check_code", "C" * 50) == Success("c" * 50)


def returns_error_when_code_has_51_characters() -> None:
    assert _call("check_code", "c" * 51) == _failed("code", "Use at most 50 characters.")


def returns_error_when_code_holds_a_null_character() -> None:
    assert _call("check_code", "ab\x00c") == _failed("code", 'Remove the character after "ab".')


def returns_trimmed_name_when_name_has_outer_spaces() -> None:
    assert _call("check_name", " Saint Anne ") == Success("Saint Anne")


def returns_error_when_name_is_blank_after_trim() -> None:
    assert _call("check_name", "   ") == _failed("name", "Enter a name.")


def returns_name_when_it_has_200_characters() -> None:
    assert _call("check_name", "n" * 200) == Success("n" * 200)


def returns_error_when_name_has_201_characters() -> None:
    assert _call("check_name", "n" * 201) == _failed("name", "Use at most 200 characters.")


def returns_lower_case_colour_when_colour_is_typed_in_capitals() -> None:
    assert _call("check_colour", "#FFAA00") == Success("#ffaa00")


@pytest.mark.parametrize("colour", ["#12345g", "#fff", "123456", "#1234567", ""])
def returns_error_when_colour_is_not_seven_characters_hex(colour: str) -> None:
    assert _call("check_colour", colour) == _failed("colour", "Use a colour like #1a2b3c.")


def returns_error_on_latitude_when_only_latitude_is_given() -> None:
    assert _call("check_coordinates", "45.5", "") == _failed(
        "longitude", "Give longitude too, or clear latitude."
    )


def returns_error_on_latitude_when_only_longitude_is_given() -> None:
    assert _call("check_coordinates", "", "2.3") == _failed(
        "latitude", "Give latitude too, or clear longitude."
    )


def returns_no_coordinates_when_both_are_empty() -> None:
    assert _call("check_coordinates", "", "") == Success((None, None))


def returns_error_when_latitude_is_91() -> None:
    assert _call("check_coordinates", "91", "0") == _failed(
        "latitude", "Use a number from -90 to 90."
    )


def returns_both_when_latitude_is_90_and_longitude_minus_180() -> None:
    assert _call("check_coordinates", "90", "-180") == Success((90.0, -180.0))


def returns_error_when_longitude_is_180_point_1() -> None:
    assert _call("check_coordinates", "0", "180.1") == _failed(
        "longitude", "Use a number from -180 to 180."
    )


def returns_error_when_latitude_is_not_a_number() -> None:
    assert _call("check_coordinates", "north", "0") == _failed(
        "latitude", "Use a number from -90 to 90."
    )


@pytest.mark.parametrize("text", ["nan", "inf"])
def returns_error_when_coordinate_is_not_finite(text: str) -> None:
    assert isinstance(_call("check_coordinates", text, "0"), Failure)


def returns_zone_when_time_zone_is_known() -> None:
    assert _call("check_time_zone", "Europe/Paris", KNOWN_ZONES) == Success("Europe/Paris")


def returns_error_when_time_zone_is_unknown() -> None:
    assert _call("check_time_zone", "Mars/Olympus", KNOWN_ZONES) == _failed(
        "time_zone", "Choose a time zone from the list."
    )


def returns_error_when_capacity_is_0() -> None:
    assert _call("check_capacity", "0") == _failed("capacity", "Use a whole number of 1 or more.")


def returns_capacity_when_it_is_1() -> None:
    assert _call("check_capacity", "1") == Success(1)


def returns_error_when_capacity_is_not_a_whole_number() -> None:
    assert _call("check_capacity", "1.5").__class__ is Failure


def returns_error_when_duration_is_0() -> None:
    assert _call("check_duration_minutes", "0") == _failed(
        "duration_minutes", "Use a whole number of 1 or more."
    )


def returns_duration_when_it_is_1() -> None:
    assert _call("check_duration_minutes", "1") == Success(1)


def returns_error_when_buffer_is_minus_1() -> None:
    assert _call("check_buffer_minutes", "-1") == _failed(
        "buffer_minutes", "Use a whole number of 0 or more."
    )


def returns_buffer_when_it_is_0() -> None:
    assert _call("check_buffer_minutes", "0") == Success(0)


def returns_invalid_input_code_when_any_check_fails() -> None:
    failure = _call("check_capacity", "x")

    assert isinstance(failure, Failure) and failure.code == FailureCode.INVALID_INPUT


def returns_error_when_text_holds_a_null_character() -> None:
    assert _call("check_name", "a\x00b") == _failed("name", 'Remove the character after "a".')


def returns_error_on_equipment_when_it_holds_a_null_character() -> None:
    assert _call("check_equipment", "scanner\x00") == _failed(
        "equipment", 'Remove the character after "scanner".'
    )


def returns_items_without_blank_lines_when_equipment_has_two_lines() -> None:
    assert _call("check_equipment", " scanner \n\n bed ") == Success(["scanner", "bed"])


def returns_error_when_an_equipment_line_has_101_characters() -> None:
    assert _call("check_equipment", "scanner\n" + "e" * 101) == _failed(
        "equipment", "Use at most 100 characters on a line."
    )


def returns_the_line_when_an_equipment_line_has_100_characters() -> None:
    assert _call("check_equipment", "e" * 100) == Success(["e" * 100])


def returns_no_items_when_equipment_is_blank() -> None:
    assert _call("check_equipment", "  \n ") == Success([])


def returns_capacity_when_it_is_the_largest_stored_number() -> None:
    assert _call("check_capacity", " 32767 ") == Success(32767)


def returns_error_when_capacity_is_32768() -> None:
    assert _call("check_capacity", "32768") == _failed(
        "capacity", "Use a whole number of at most 32767."
    )


def returns_error_when_buffer_is_not_a_number() -> None:
    assert _call("check_buffer_minutes", "x") == _failed(
        "buffer_minutes", "Use a whole number of 0 or more."
    )


def returns_lower_case_colour_when_colour_has_outer_spaces() -> None:
    assert _call("check_colour", " #ABCDEF ") == Success("#abcdef")


def returns_error_when_colour_has_seven_characters_and_no_hash() -> None:
    assert _call("check_colour", "1234567") == _failed("colour", "Use a colour like #1a2b3c.")


def returns_error_when_colour_has_a_hash_inside() -> None:
    assert _call("check_colour", "#12#456") == _failed("colour", "Use a colour like #1a2b3c.")


def returns_error_when_the_first_colour_digit_is_not_hex() -> None:
    assert _call("check_colour", "#g12345") == _failed("colour", "Use a colour like #1a2b3c.")


def returns_message_on_field_when_a_single_line_text_holds_a_line_break() -> None:
    assert _call("check_name", "Main\nWing") == _failed(
        "name", 'This field takes one line. Remove the line break after "Main".'
    )


def returns_message_on_code_when_a_code_holds_a_line_break() -> None:
    assert _call("check_code", "ab\ncd") == _failed(
        "code", 'This field takes one line. Remove the line break after "ab".'
    )
