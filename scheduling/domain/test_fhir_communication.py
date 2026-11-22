"""Task 24: `decode_update` refuses a `received` that is not a date-time, whatever its type."""

from datetime import UTC, datetime
from uuid import uuid4

from scheduling.domain.fhir_communication import (
    KIND_SYSTEM,
    NOTIFICATION_KIND_WORDS,
    CommunicationFacts,
    MarkRead,
    NoChange,
    communication_resource,
    decode_update,
)
from scheduling.models.booking import NotificationKind


def returns_the_dotted_name_when_received_is_not_a_string() -> None:
    body: dict[str, object] = {"status": "completed", "received": 7}

    assert decode_update({"status": "completed"}, body) == "Communication.received"


def returns_mark_read_when_received_is_a_date_time_and_nothing_else_changed() -> None:
    body: dict[str, object] = {"status": "completed", "received": "2030-01-07T06:00:00Z"}

    assert decode_update({"status": "completed"}, body) == MarkRead()


def returns_the_dotted_name_when_received_is_a_malformed_string() -> None:
    body: dict[str, object] = {"status": "completed", "received": "yesterday"}

    assert decode_update({"status": "completed"}, body) == "Communication.received"


def returns_the_dotted_name_when_received_changes_after_it_was_set() -> None:
    stored: dict[str, object] = {"status": "completed", "received": "2030-01-07T06:00:00Z"}
    body: dict[str, object] = {"status": "completed", "received": "2030-01-08T06:00:00Z"}

    assert decode_update(stored, body) == "Communication.received"


def returns_words_as_display_and_the_code_unchanged_when_category_is_built() -> None:
    moment = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
    facts = CommunicationFacts(
        uuid4(), 1, moment, "SCHEDULE_CHANGED", "Patient", uuid4(), "t", "", moment, None, None
    )

    coding = communication_resource(facts)["category"][0]["coding"][0]  # type: ignore[index]

    assert (coding["code"], coding["display"]) == ("SCHEDULE_CHANGED", "Schedule changed")


def returns_words_for_every_notification_kind() -> None:
    assert set(NOTIFICATION_KIND_WORDS) == {kind.value for kind in NotificationKind}


def returns_no_change_when_received_equals_the_stored_received() -> None:
    stored: dict[str, object] = {"status": "completed", "received": "2030-01-07T06:00:00Z"}

    assert decode_update(stored, dict(stored)) == NoChange()


def returns_the_dotted_name_when_the_body_drops_a_stored_element() -> None:
    stored: dict[str, object] = {"status": "completed", "sent": "2030-01-07T06:00:00Z"}

    assert decode_update(stored, {"status": "completed"}) == "Communication.sent"


def returns_the_dotted_name_when_the_body_adds_an_element() -> None:
    body: dict[str, object] = {"status": "completed", "sent": "2030-01-07T06:00:00Z"}

    assert decode_update({"status": "completed"}, body) == "Communication.sent"


def returns_the_whole_resource_when_every_fact_is_present() -> None:
    moment = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
    identifier, recipient, about = uuid4(), uuid4(), uuid4()
    facts = CommunicationFacts(
        identifier,
        3,
        moment,
        "WAITLIST_BOOKED",
        "Patient",
        recipient,
        "Title",
        "Body",
        moment,
        moment,
        about,
    )

    assert communication_resource(facts) == {
        "resourceType": "Communication",
        "id": str(identifier),
        "meta": {"versionId": "3", "lastUpdated": "2030-01-07T06:00:00.000Z"},
        "status": "completed",
        "category": [
            {
                "coding": [
                    {
                        "system": KIND_SYSTEM,
                        "code": "WAITLIST_BOOKED",
                        "display": "Waitlist booked",
                    }
                ]
            }
        ],
        "recipient": [{"reference": f"Patient/{recipient}"}],
        "payload": [{"contentString": "Title\nBody"}],
        "sent": "2030-01-07T06:00:00.000Z",
        "about": [{"reference": f"Appointment/{about}"}],
        "received": "2030-01-07T06:00:00.000Z",
    }


def returns_only_the_title_and_no_optional_elements_when_body_and_links_are_absent() -> None:
    moment = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
    facts = CommunicationFacts(
        uuid4(),
        1,
        moment,
        "SCHEDULE_CHANGED",
        "Practitioner",
        uuid4(),
        "Title",
        "",
        moment,
        None,
        None,
    )

    resource = communication_resource(facts)

    assert resource["payload"] == [{"contentString": "Title"}]
    assert {"about", "received"} & set(resource) == set()
    assert resource["recipient"][0]["reference"].startswith("Practitioner/")  # type: ignore[index]
