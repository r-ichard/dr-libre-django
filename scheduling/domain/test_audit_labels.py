"""Section 9.3: the history shows a plain label for each audit action."""


def returns_plain_label_when_action_is_known() -> None:
    from scheduling.domain.audit_labels import audit_label

    assert audit_label("appointment.check_in") == "Checked in"
    assert audit_label("appointment.note_save") == "Clinical note saved"
    assert audit_label("appointment.cancel") == "Cancelled"


def returns_generic_words_when_action_is_unknown() -> None:
    from scheduling.domain.audit_labels import audit_label

    assert audit_label("appointment.invented") == "Changed the record"


def returns_booked_when_action_is_appointment_book() -> None:
    from scheduling.domain.audit_labels import audit_label

    assert audit_label("appointment.book") == "Booked"


def returns_plain_words_when_action_has_no_label() -> None:
    from scheduling.domain.audit_labels import audit_label

    assert "." not in audit_label("appointment.invented")
