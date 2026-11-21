from datetime import UTC, datetime

import pytest

from scheduling.domain.request_context import RequestContext, is_sane_correlation_id


@pytest.mark.parametrize("candidate", ["", "a" * 65, "a b", "a\nb", "é", "a/b", "a;b"])
def returns_false_when_correlation_id_is_empty_too_long_or_has_unsafe_characters(
    candidate: str,
) -> None:
    assert is_sane_correlation_id(candidate) is False


@pytest.mark.parametrize("candidate", ["a", "Az09._-" * 9 + "x", "a" * 64, "req-1.2_3"])
def returns_true_when_correlation_id_is_up_to_64_letters_digits_dot_dash_underscore(
    candidate: str,
) -> None:
    assert is_sane_correlation_id(candidate) is True


def raises_when_request_context_instant_is_naive() -> None:
    with pytest.raises(ValueError, match="aware"):
        RequestContext(correlation_id="abc", now=datetime(2026, 1, 1, 12, 0))  # noqa: DTZ001


def returns_context_values_when_instant_is_aware() -> None:
    instant = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    context = RequestContext(correlation_id="abc", now=instant)

    assert (context.correlation_id, context.now) == ("abc", instant)
