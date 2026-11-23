"""Sections 15.2, 15.4, 15.5: a patient changes phone and birth date only; any other element
that differs from the stored record is named."""

from datetime import date

from scheduling.domain.fhir_patient import PatientValues, patient_values, refused_changes

STORED = {
    "resourceType": "Patient",
    "id": "p1",
    "meta": {"versionId": "3"},
    "active": True,
    "name": [{"text": "Ada Patient"}],
    "birthDate": "1990-01-01",
    "telecom": [{"system": "email", "value": "a@example.org"}],
}
PATIENT_MAY_CHANGE = ("birthDate", "telecom")


def returns_nothing_when_only_birth_date_changes() -> None:
    body = {**STORED, "birthDate": "1991-01-01"}

    assert refused_changes(STORED, body, PATIENT_MAY_CHANGE) == ()


def returns_name_element_when_name_changes() -> None:
    body = {**STORED, "name": [{"text": "Other Name"}]}

    assert refused_changes(STORED, body, PATIENT_MAY_CHANGE) == ("Patient.name",)


def returns_active_element_when_active_changes() -> None:
    assert refused_changes(STORED, {**STORED, "active": False}, PATIENT_MAY_CHANGE) == (
        "Patient.active",
    )


def returns_email_when_telecom_email_changes_and_phone_is_added() -> None:
    body = {
        **STORED,
        "telecom": [
            {"system": "email", "value": "b@example.org"},
            {"system": "phone", "value": "+49 1"},
        ],
    }

    assert refused_changes(STORED, body, PATIENT_MAY_CHANGE) == ("Patient.telecom.email",)


def returns_nothing_when_only_meta_differs_because_the_server_owns_it() -> None:
    body = {**STORED, "meta": {"versionId": "99"}}

    assert refused_changes(STORED, body, PATIENT_MAY_CHANGE) == ()


def returns_nothing_when_an_admin_changes_the_email() -> None:
    body = {**STORED, "telecom": [{"system": "email", "value": "new@example.org"}]}

    assert refused_changes(STORED, body, ("telecom.email",)) == ()
    assert refused_changes(STORED, body, PATIENT_MAY_CHANGE) == ("Patient.telecom.email",)


def returns_the_stored_difference_when_telecom_is_not_a_list() -> None:
    body = {**STORED, "telecom": "a@example.org"}

    assert refused_changes(STORED, body, ("birthDate",)) == ("Patient.telecom.email",)


def returns_the_telecom_element_when_a_telecom_item_is_not_email_or_phone() -> None:
    fax = {**STORED, "telecom": [{"system": "fax", "value": "1"}]}

    assert patient_values(fax) == "Patient.telecom"


FULL = {
    **STORED,
    "name": [{"text": "Ada Patient"}],
    "telecom": [
        {"system": "email", "value": "a@example.org"},
        {"system": "phone", "value": "+49 30 1234"},
    ],
}


def returns_every_value_the_body_holds() -> None:
    assert patient_values(FULL) == PatientValues(
        "Ada Patient", "a@example.org", "+49 30 1234", date(1990, 1, 1), True
    )


def returns_empty_values_and_active_when_the_body_holds_nothing() -> None:
    assert patient_values({}) == PatientValues("", "", "", None, True)


def returns_inactive_only_when_active_is_exactly_false() -> None:
    assert patient_values({"active": False}) == PatientValues("", "", "", None, False)
    assert patient_values({"active": "no"}) == PatientValues("", "", "", None, False)


def returns_the_first_name_text() -> None:
    body: dict[str, object] = {"name": [{"text": "First"}, {"text": "Second"}]}

    assert patient_values(body) == PatientValues("First", "", "", None, True)


def returns_empty_name_when_name_is_empty_or_has_no_text() -> None:
    assert patient_values({"name": []}) == PatientValues("", "", "", None, True)
    assert patient_values({"name": [{}]}) == PatientValues("", "", "", None, True)


def returns_birth_date_element_when_it_is_not_a_calendar_day() -> None:
    for text in ("1990-13-01", "1990-1-1", "19900101", " 1990-01-01", "1990-01-01 "):
        assert patient_values({"birthDate": text}) == "Patient.birthDate"
    assert patient_values({"birthDate": 1990}) == "Patient.birthDate"


def returns_telecom_element_when_an_item_repeats_or_has_no_text_value() -> None:
    twice = [{"system": "email", "value": "a@x.org"}, {"system": "email", "value": "b@x.org"}]

    assert patient_values({"telecom": twice}) == "Patient.telecom"
    assert patient_values({"telecom": [{"system": "email", "value": 5}]}) == "Patient.telecom"
    assert patient_values({"telecom": "a@x.org"}) == PatientValues("", "", "", None, True)
