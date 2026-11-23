from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts.smoke import Journey, Reply, SmokeFailure, cancel_step, hold_step
from scripts.test_smoke import (
    APPOINTMENT_ID,
    HOLD_ANSWER,
    INSTANT_FORMAT,
    PROVIDER_ID,
    FakeStack,
    _hold_stack,
    _json,
)


def returns_search_window_starting_25_hours_from_now_when_holding() -> None:
    stack = _hold_stack(HOLD_ANSWER)
    before = datetime.now(UTC).replace(tzinfo=None)

    hold_step(Journey(fetch=stack, provider_id=PROVIDER_ID))

    after = datetime.now(UTC).replace(tzinfo=None)
    slots_url = next(url for _, url, _ in stack.sent if "/api/v1/slots" in url)
    window = parse_qs(urlsplit(slots_url).query)
    starts = datetime.strptime(window["from"][0], INSTANT_FORMAT)
    assert before + timedelta(hours=25) - timedelta(seconds=1) <= starts
    assert starts <= after + timedelta(hours=25)


def raises_smoke_failure_naming_code_and_violated_rules_when_cancel_is_refused() -> None:
    refusal = _json(
        {
            "error": {
                "code": "rule_violation",
                "details": {"violated_rules": ["cancellation_window_closed"]},
            }
        }
    )
    stack = FakeStack({("POST", "/cancel"): Reply(422, refusal)})

    with pytest.raises(SmokeFailure) as failure:
        cancel_step(Journey(fetch=stack, appointment_id=APPOINTMENT_ID))

    assert str(failure.value) == (
        "cancel answered 422, wanted 200: rule_violation; "
        "violated rules: cancellation_window_closed"
    )


def raises_smoke_failure_naming_code_without_rules_when_refusal_lists_no_rules() -> None:
    refusal = _json({"error": {"code": "conflict", "details": {}}})
    stack = FakeStack({("POST", "/cancel"): Reply(409, refusal)})

    with pytest.raises(SmokeFailure) as failure:
        cancel_step(Journey(fetch=stack, appointment_id=APPOINTMENT_ID))

    assert str(failure.value) == "cancel answered 409, wanted 200: conflict"


def returns_message_naming_only_text_rules_when_rules_mix_types() -> None:
    refusal = _json(
        {
            "error": {
                "code": "rule_violation",
                "details": {"violated_rules": ["cancellation_window_closed", 7]},
            }
        }
    )
    stack = FakeStack({("POST", "/cancel"): Reply(422, refusal)})

    with pytest.raises(SmokeFailure) as failure:
        cancel_step(Journey(fetch=stack, appointment_id=APPOINTMENT_ID))

    assert str(failure.value) == (
        "cancel answered 422, wanted 200: rule_violation; "
        "violated rules: cancellation_window_closed"
    )


@pytest.mark.parametrize(
    "refusal_body",
    [
        pytest.param("<html>Server Error</html>", id="not_json"),
        pytest.param(_json(["error"]), id="top_level_not_object"),
        pytest.param(_json({"error": "boom"}), id="error_not_object"),
        pytest.param(_json({"error": {"code": 7}}), id="code_not_string"),
    ],
)
def returns_status_only_message_when_refusal_body_has_no_usable_error(refusal_body: str) -> None:
    stack = FakeStack({("POST", "/cancel"): Reply(500, refusal_body)})

    with pytest.raises(SmokeFailure) as failure:
        cancel_step(Journey(fetch=stack, appointment_id=APPOINTMENT_ID))

    assert str(failure.value) == "cancel answered 500, wanted 200"
