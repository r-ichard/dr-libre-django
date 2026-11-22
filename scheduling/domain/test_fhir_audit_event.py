"""Task 24a, points 1 and 5: the product action stays in `type`, `action` is one code, and
`entity.detail` serves only the keys `AuditMetadata` can emit."""

from datetime import UTC, datetime
from uuid import uuid4

from scheduling.domain.audit_metadata import METADATA_KEYS, AuditMetadata
from scheduling.domain.fhir_audit_event import (
    ACTION_SYSTEM,
    ENTITY_SYSTEM,
    AuditFacts,
    audit_event_resource,
)
from scheduling.domain.fhir_common import extension_url

MOMENT = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)


def _facts(metadata: dict[str, object]) -> AuditFacts:
    return AuditFacts(
        uuid4(),
        1,
        MOMENT,
        MOMENT,
        "appointment.book",
        None,
        None,
        "appointment",
        "x",
        metadata,
        "c",
    )


def returns_type_code_with_product_action_and_one_letter_action_when_event_is_built() -> None:
    event = audit_event_resource(_facts({}))

    assert (event["type"]["code"], event["action"]) == ("appointment.book", "C")  # type: ignore[index]


def returns_only_named_detail_keys_when_metadata_holds_an_unlisted_key() -> None:
    metadata: dict[str, object] = {"counts": {"slot_count": 2}, "note": "private", "name": "Ada"}

    event = audit_event_resource(_facts(metadata))

    details = event["entity"][0]["detail"]  # type: ignore[index]
    assert [(item["type"], item["valueString"]) for item in details] == [("slot_count", "2")]


def returns_keys_of_to_json_when_the_allow_list_is_read() -> None:
    assert set(METADATA_KEYS) == set(AuditMetadata().to_json())


def returns_the_whole_event_when_an_actor_and_every_metadata_section_are_present() -> None:
    identifier, actor = uuid4(), uuid4()
    facts = AuditFacts(
        identifier,
        2,
        MOMENT,
        MOMENT,
        "appointment.cancel",
        "Practitioner",
        actor,
        "appointment",
        "entity-1",
        {
            "ids": {"appointment_id": "a1"},
            "counts": {"slot_count": 0},
            "statuses": {},
            "changed_fields": ["status", "reason"],
            "email_domain": "example.org",
        },
        "corr-1",
    )

    assert audit_event_resource(facts) == {
        "resourceType": "AuditEvent",
        "id": str(identifier),
        "meta": {"versionId": "2", "lastUpdated": "2030-01-07T06:00:00.000Z"},
        "type": {"system": ACTION_SYSTEM, "code": "appointment.cancel"},
        "action": "U",
        "recorded": "2030-01-07T06:00:00.000Z",
        "agent": [{"requestor": True, "who": {"reference": f"Practitioner/{actor}"}}],
        "source": {"observer": {"display": "DrLibre"}},
        "entity": [
            {
                "what": {"identifier": {"system": ENTITY_SYSTEM, "value": "entity-1"}},
                "type": {"system": ENTITY_SYSTEM, "code": "appointment"},
                "detail": [
                    {"type": "appointment_id", "valueString": "a1"},
                    {"type": "slot_count", "valueString": "0"},
                    {"type": "changed_fields", "valueString": "status, reason"},
                    {"type": "email_domain", "valueString": "example.org"},
                ],
            }
        ],
        "extension": [
            {"url": extension_url("correlation-id"), "valueString": "corr-1"},
        ],
    }


def returns_an_agent_without_who_when_the_actor_is_unknown() -> None:
    event = audit_event_resource(_facts({}))

    assert event["agent"] == [{"requestor": True}]
    assert "detail" not in event["entity"][0]  # type: ignore[index]


def returns_no_who_when_only_one_of_actor_type_and_actor_id_is_known() -> None:
    only_id = AuditFacts(
        uuid4(), 1, MOMENT, MOMENT, "appointment.book", None, uuid4(), "appointment", "x", {}, "c"
    )
    only_type = AuditFacts(
        uuid4(), 1, MOMENT, MOMENT, "appointment.book", "Patient", None, "appointment", "x", {}, "c"
    )

    assert audit_event_resource(only_id)["agent"] == [{"requestor": True}]
    assert audit_event_resource(only_type)["agent"] == [{"requestor": True}]


def returns_keys_after_an_unlisted_key_when_metadata_is_walked() -> None:
    metadata: dict[str, object] = {"note": "private", "counts": {"slot_count": 2}}

    details = audit_event_resource(_facts(metadata))["entity"][0]["detail"]  # type: ignore[index]

    assert [item["type"] for item in details] == ["slot_count"]
