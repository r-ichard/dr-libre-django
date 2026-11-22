"""Task 21, #14: the audited record types come from one registry."""


def returns_lists_sign_in_link_among_audited_entity_types() -> None:
    from scheduling.domain.audit_entity_types import AUDITED_ENTITY_TYPES

    assert "SignInLink" in AUDITED_ENTITY_TYPES
    assert "Appointment" in AUDITED_ENTITY_TYPES
