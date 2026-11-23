import pytest

from drlibre.time_gate import over_limit_message

NODEID = "scheduling/domain/test_x.py::returns_y"
LIMIT_SECONDS = 60


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def returns_message_naming_test_phase_seconds_and_limit_when_phase_takes_over_limit(
    phase: str,
) -> None:
    message = over_limit_message(NODEID, phase, 61.5, LIMIT_SECONDS)

    assert message is not None
    assert NODEID in message
    assert phase in message
    assert "61.5 s" in message
    assert "60 s" in message


def returns_none_when_call_takes_under_limit() -> None:
    message = over_limit_message(NODEID, "call", 11.5, LIMIT_SECONDS)

    assert message is None


def returns_none_when_call_takes_exactly_limit() -> None:
    message = over_limit_message(NODEID, "call", 5, 5)

    assert message is None
