"""Section 15.6: slot id built from schedule, type and start only, and parses back."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from scheduling.domain.fhir_slot_id import parse_slot_id, slot_id

RULE = UUID("11111111-1111-4111-8111-111111111111")
TYPE = UUID("22222222-2222-4222-8222-222222222222")
START = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)


def returns_same_id_for_same_schedule_type_and_start() -> None:
    assert slot_id(RULE, TYPE, START) == slot_id(RULE, TYPE, START)


def returns_different_ids_when_any_of_the_three_differs() -> None:
    ids = {
        slot_id(RULE, TYPE, START),
        slot_id(uuid4(), TYPE, START),
        slot_id(RULE, uuid4(), START),
        slot_id(RULE, TYPE, START + timedelta(minutes=15)),
    }

    assert len(ids) == 4


def returns_three_dot_parts_inside_the_fhir_id_alphabet_and_length() -> None:
    identifier = slot_id(RULE, TYPE, START)

    assert len(identifier) <= 64
    assert len(identifier.split(".")) == 3
    assert identifier.split(".")[2] == str(int(START.timestamp() // 60))
    assert all(char.isalnum() or char == "." for char in identifier)
    assert str(RULE) not in identifier


@pytest.mark.parametrize("minutes", [0, 1, 28_000_000, 29_000_000])
def returns_the_three_parts_when_a_built_id_is_parsed(minutes: int) -> None:
    start = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(minutes=minutes)

    assert parse_slot_id(slot_id(RULE, TYPE, start)) == (RULE, TYPE, start)


@pytest.mark.parametrize(
    "text",
    ["", "a", "a.b", "a.b.c.d", "!!.@@.12", "11111111111111111111111111.2222222222.x"],
)
def returns_none_when_id_does_not_parse(text: str) -> None:
    assert parse_slot_id(text) is None


def returns_none_when_a_part_has_bad_base32_or_wrong_length() -> None:
    good = slot_id(RULE, TYPE, START)
    rule_part, type_part, minutes = good.split(".")

    assert parse_slot_id(f"{rule_part[:-1]}.{type_part}.{minutes}") is None
    assert parse_slot_id(f"{rule_part[:-1]}1.{type_part}.{minutes}") is None
    assert parse_slot_id(f"{rule_part}.{type_part}.{minutes}0000000000") is None


def returns_lower_case_letters_and_digits_only() -> None:
    rule_part, type_part, _ = slot_id(RULE, TYPE, START).split(".")

    assert rule_part == rule_part.lower()
    assert type_part == type_part.lower()


def returns_none_when_a_part_is_upper_case_or_not_the_canonical_spelling() -> None:
    rule_part, type_part, minutes = slot_id(RULE, TYPE, START).split(".")
    next_letter = rule_part[:-1] + chr(ord(rule_part[-1]) + 1)

    assert parse_slot_id(f"{rule_part.upper()}.{type_part}.{minutes}") is None
    assert parse_slot_id(f"{next_letter}.{type_part}.{minutes}") is None


def returns_the_three_parts_when_the_minutes_have_ten_digits() -> None:
    start = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(minutes=1_000_000_000)

    assert parse_slot_id(slot_id(RULE, TYPE, start)) == (RULE, TYPE, start)
