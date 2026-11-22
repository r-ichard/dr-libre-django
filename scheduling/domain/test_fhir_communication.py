"""Task 24: `decode_update` refuses a `received` that is not a date-time, whatever its type."""

from scheduling.domain.fhir_communication import MarkRead, decode_update


def returns_the_dotted_name_when_received_is_not_a_string() -> None:
    body: dict[str, object] = {"status": "completed", "received": 7}

    assert decode_update({"status": "completed"}, body) == "Communication.received"


def returns_mark_read_when_received_is_a_date_time_and_nothing_else_changed() -> None:
    body: dict[str, object] = {"status": "completed", "received": "2030-01-07T06:00:00Z"}

    assert decode_update({"status": "completed"}, body) == MarkRead()
