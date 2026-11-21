from pathlib import Path

import pytest

from scripts.size_cap import MAXIMUM_FILE_LINES, MAXIMUM_FUNCTION_LINES, main, size_violations


def _file_of(line_count: int) -> str:
    return "\n".join(f"value_{number} = {number}" for number in range(line_count)) + "\n"


def _function_of(line_count: int) -> str:
    body = "\n".join("    total += 1" for _ in range(line_count - 3))
    return f"def counter() -> int:\n    total = 0\n{body}\n    return total\n"


def returns_limits_of_500_file_lines_and_100_function_lines() -> None:
    assert (MAXIMUM_FILE_LINES, MAXIMUM_FUNCTION_LINES) == (500, 100)


def returns_no_violation_when_file_has_500_lines() -> None:
    assert size_violations("scheduling/big.py", _file_of(500)) == []


def returns_a_violation_naming_the_file_when_file_has_501_lines() -> None:
    violations = size_violations("scheduling/big.py", _file_of(501))

    assert len(violations) == 1
    assert "scheduling/big.py" in violations[0]
    assert "501" in violations[0]


def returns_no_violation_when_function_has_100_lines() -> None:
    source = _function_of(100)
    assert len(source.splitlines()) == 100

    assert size_violations("scheduling/long.py", source) == []


def returns_a_violation_naming_the_function_when_function_has_101_lines() -> None:
    source = _function_of(101)
    assert len(source.splitlines()) == 101

    violations = size_violations("scheduling/long.py", source)

    assert len(violations) == 1
    assert "counter" in violations[0]
    assert "101" in violations[0]


def returns_a_violation_when_a_method_has_101_lines() -> None:
    method = "\n".join(f"    {line}" if line else line for line in _function_of(101).splitlines())

    violations = size_violations("scheduling/long.py", f"class Holder:\n{method}\n")

    assert len(violations) == 1
    assert "counter" in violations[0]


@pytest.mark.parametrize("source", [_file_of(900), _function_of(150)])
def returns_no_violation_when_the_file_is_a_generated_migration(source: str) -> None:
    assert size_violations("scheduling/migrations/0001_initial.py", source) == []


def returns_a_violation_when_an_async_function_has_101_lines() -> None:
    source = "async " + _function_of(MAXIMUM_FUNCTION_LINES + 1)

    violations = size_violations("scheduling/jobs.py", source)

    assert len(violations) == 1
    assert "counter" in violations[0]


def returns_1_when_a_listed_file_is_too_long(tmp_path: Path) -> None:
    long_file = tmp_path / "long.py"
    long_file.write_text(_file_of(MAXIMUM_FILE_LINES + 1), encoding="utf-8")

    assert main([str(long_file)]) == 1


def returns_0_when_every_listed_file_is_within_limits(tmp_path: Path) -> None:
    short_file = tmp_path / "short.py"
    short_file.write_text(_file_of(3), encoding="utf-8")

    assert main([str(short_file)]) == 0
