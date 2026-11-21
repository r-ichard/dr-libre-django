from scheduling.domain.failure import Failure, FailureCode, FieldMessage, Success

SPECIFICATION_CODES = {
    "invalid_input",
    "unauthenticated",
    "forbidden",
    "not_found",
    "conflict",
    "no_room_available",
    "no_clinician_available",
    "invalid_transition",
    "has_dependents",
    "rule_violation",
    "rate_limited",
    "mail_unavailable",
}


def returns_exactly_the_twelve_specified_codes_when_failure_codes_are_listed() -> None:
    listed = {code.value for code in FailureCode}

    assert listed == SPECIFICATION_CODES


def returns_invalid_input_with_field_messages_when_invalid_input_constructor_is_called() -> None:
    message = FieldMessage(field="start", message="This field is required.")

    failure = Failure.invalid_input([message])

    assert failure.code == FailureCode.INVALID_INPUT
    assert failure.details == {"fields": [{"field": "start", "message": "This field is required."}]}


def returns_resources_in_conflict_when_conflict_constructor_is_called() -> None:
    failure = Failure.conflict(["clinician", "room"])

    assert failure.code == FailureCode.CONFLICT
    assert failure.details == {"resources": ["clinician", "room"]}


def returns_current_status_when_invalid_transition_constructor_is_called() -> None:
    failure = Failure.invalid_transition("completed")

    assert failure.code == FailureCode.INVALID_TRANSITION
    assert failure.details == {"current_status": "completed"}


def returns_dependents_when_has_dependents_constructor_is_called() -> None:
    failure = Failure.has_dependents(["appointments", "waitlist_entries"])

    assert failure.details == {"dependents": ["appointments", "waitlist_entries"]}


def returns_violated_rules_when_rule_violation_constructor_is_called() -> None:
    failure = Failure.rule_violation(["lead_time", "daily_limit"])

    assert failure.details == {"violated_rules": ["lead_time", "daily_limit"]}


def returns_empty_details_when_code_carries_no_details() -> None:
    failures = [
        Failure.unauthenticated(),
        Failure.forbidden(),
        Failure.not_found(),
        Failure.no_room_available(),
        Failure.no_clinician_available(),
    ]

    assert [failure.details for failure in failures] == [{}, {}, {}, {}, {}]


def returns_wrapped_value_when_success_is_built() -> None:
    assert Success("booked").value == "booked"


def returns_rate_limited_with_empty_details_when_rate_limited_constructor_is_called() -> None:
    failure = Failure.rate_limited()

    assert failure.code.value == "rate_limited"
    assert failure.details == {}


def returns_mail_unavailable_with_empty_details_when_mail_unavailable_constructor_is_called() -> (
    None
):
    failure = Failure.mail_unavailable()

    assert failure.code.value == "mail_unavailable"
    assert failure.details == {}
