import time
import uuid


def returns_version_7_uuid_when_identifier_is_generated() -> None:
    from scheduling.identifiers import new_identifier

    identifier = new_identifier()

    assert isinstance(identifier, uuid.UUID)
    assert identifier.version == 7
    assert identifier.variant == uuid.RFC_4122


def returns_later_sorting_identifier_when_generated_after_a_pause() -> None:
    from scheduling.identifiers import new_identifier

    first = new_identifier()
    time.sleep(0.005)
    second = new_identifier()

    assert first < second


def returns_distinct_identifiers_when_generated_in_the_same_millisecond() -> None:
    from scheduling.identifiers import new_identifier

    identifiers = {new_identifier() for _ in range(1000)}

    assert len(identifiers) == 1000
