"""Section 4: audit metadata holds only ids, counts, statuses and field names, and an
email domain. Each forbidden kind (name, email, phone, birth date, reason, note) is tried."""

from datetime import date
from enum import StrEnum
from uuid import UUID

import pytest

from scheduling.domain.audit_metadata import AuditMetadata, email_domain, field_name

APPOINTMENT_ID = UUID("0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b")


class BookingStatus(StrEnum):
    BOOKED = "BOOKED"


def returns_json_with_ids_counts_statuses_fields_when_metadata_is_built() -> None:
    metadata = AuditMetadata(
        ids={"appointment_id": APPOINTMENT_ID},
        counts={"row_count": 3},
        statuses={"new_status": BookingStatus.BOOKED},
        changed_fields=(field_name("starts_at"),),
        email_domain=email_domain("jane@example.test"),
    )

    serialised = metadata.to_json()

    assert serialised == {
        "ids": {"appointment_id": str(APPOINTMENT_ID)},
        "counts": {"row_count": 3},
        "statuses": {"new_status": "BOOKED"},
        "changed_fields": ["starts_at"],
        "email_domain": "example.test",
    }


def returns_empty_sections_when_metadata_is_built_without_values() -> None:
    serialised = AuditMetadata().to_json()

    assert serialised == {
        "ids": {},
        "counts": {},
        "statuses": {},
        "changed_fields": [],
        "email_domain": None,
    }


def returns_domain_only_when_address_is_given() -> None:
    domain = email_domain("jane.doe@example.test")

    serialised = AuditMetadata(email_domain=domain).to_json()

    assert serialised["email_domain"] == "example.test"
    assert "jane" not in str(serialised)


def rejects_email_domain_when_input_has_no_at_sign() -> None:
    with pytest.raises(ValueError):
        email_domain("example.test")


def rejects_email_domain_with_clinical_note_text() -> None:
    with pytest.raises(ValueError):
        email_domain("x@patient has chest pain")


def rejects_free_text_status_when_a_plain_string_is_given() -> None:
    with pytest.raises(ValueError):
        AuditMetadata(statuses={"new_status": "patient asked to cancel"})  # type: ignore[dict-item]


@pytest.mark.parametrize(
    "forbidden", ["Jane Doe", "jane@example.test", "+33 6 12 34 56 78", "1990-01-02"]
)
def rejects_name_as_field_name_when_it_does_not_match_the_pattern(forbidden: str) -> None:
    with pytest.raises(ValueError):
        field_name(forbidden)


def rejects_phone_number_when_passed_as_id() -> None:
    with pytest.raises(ValueError):
        AuditMetadata(ids={"patient_id": "+33 6 12 34 56 78"})  # type: ignore[dict-item]


def rejects_bool_when_passed_as_count() -> None:
    with pytest.raises(ValueError):
        AuditMetadata(counts={"row_count": True})


def rejects_birth_date_when_passed_as_value() -> None:
    with pytest.raises(ValueError):
        AuditMetadata(ids={"patient_id": date(1990, 1, 2)})  # type: ignore[dict-item]
    with pytest.raises(ValueError):
        AuditMetadata(counts={"row_count": date(1990, 1, 2)})  # type: ignore[dict-item]
    with pytest.raises(ValueError):
        AuditMetadata(statuses={"new_status": date(1990, 1, 2)})  # type: ignore[dict-item]


@pytest.mark.parametrize(
    "metadata_factory",
    [
        lambda: AuditMetadata(ids={"patient_name": APPOINTMENT_ID}),
        lambda: AuditMetadata(counts={"note": 1}),
        lambda: AuditMetadata(statuses={"note_count": BookingStatus.BOOKED}),
        lambda: AuditMetadata(ids={"Jane Doe": APPOINTMENT_ID}),
    ],
)
def rejects_key_that_does_not_name_its_kind(metadata_factory: object) -> None:
    with pytest.raises(ValueError):
        metadata_factory()  # type: ignore[operator]


class ConsentStatus(StrEnum):
    GIVEN = "given_by_patient"


def returns_enum_value_not_member_name_when_status_is_serialised() -> None:
    serialised = AuditMetadata(statuses={"new_status": ConsentStatus.GIVEN}).to_json()

    assert serialised["statuses"] == {"new_status": "given_by_patient"}


def returns_lower_case_domain_when_address_has_upper_case() -> None:
    assert email_domain("Jane@Example.TEST") == "example.test"


def returns_last_domain_when_local_part_holds_an_at_sign() -> None:
    assert email_domain('"jane@home"@example.test') == "example.test"


@pytest.mark.parametrize("trailing", [" Jane Doe", "\n", "!", "1990"])
def rejects_field_name_when_valid_prefix_has_trailing_text(trailing: str) -> None:
    with pytest.raises(ValueError):
        field_name("starts_at" + trailing)


@pytest.mark.parametrize("trailing", [" Jane Doe", "\n", "!"])
def rejects_email_domain_when_valid_host_has_trailing_text(trailing: str) -> None:
    with pytest.raises(ValueError):
        email_domain("jane@example.test" + trailing)


@pytest.mark.parametrize("trailing", [" Jane Doe", "!", "1"])
def rejects_key_when_valid_name_has_trailing_text(trailing: str) -> None:
    with pytest.raises(ValueError):
        AuditMetadata(counts={"row_count" + trailing: 1})


def rejects_key_when_free_text_precedes_a_valid_suffix() -> None:
    with pytest.raises(ValueError):
        AuditMetadata(counts={"Jane Doe_count": 1})
    with pytest.raises(ValueError):
        AuditMetadata(counts={"row count_count": 1})


@pytest.mark.parametrize("forbidden", ["Jane Doe", "jane@example.test", "+33 6 12 34 56 78"])
def rejects_changed_field_when_it_is_not_a_field_name(forbidden: str) -> None:
    with pytest.raises(ValueError):
        AuditMetadata(changed_fields=(forbidden,))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "forbidden", ["jane@example.test", "patient has chest pain", "Example.test"]
)
def rejects_email_domain_when_it_is_an_address_or_text(forbidden: str) -> None:
    with pytest.raises(ValueError):
        AuditMetadata(email_domain=forbidden)  # type: ignore[arg-type]
