"""Task 20, items 3 and 7: the patient search of the admin booking and waitlist pages."""

import pytest

from scheduling.models.builders import make
from scheduling.use_cases.admin_waitlist import active_patient, search_patients

pytestmark = pytest.mark.django_db


def returns_nobody_when_the_text_is_empty() -> None:
    make("User", full_name="Somebody")

    assert search_patients("") == []


def returns_only_active_patients_when_searching_by_name_or_email() -> None:
    active = make("User", full_name="Wanda Active", email="wanda@example.org")
    make("User", full_name="Wanda Gone", email="gone@example.org", is_active=False)
    make("User", full_name="Wanda Staff", email="staff@example.org", role="CLINICIAN")

    assert search_patients("wanda") == [active]
    assert search_patients("WANDA@example") == [active]


def returns_the_name_match_when_only_the_name_holds_the_text() -> None:
    named = make("User", full_name="Quentin Zed", email="q1@example.org")

    assert search_patients("Quentin") == [named]


def returns_the_email_match_when_only_the_email_holds_the_text() -> None:
    mailed = make("User", full_name="Plain Name", email="needle-7@example.org")

    assert search_patients("needle-7") == [mailed]


def returns_at_most_the_result_limit_when_more_patients_match() -> None:
    for index in range(21):
        make("User", full_name=f"Many {index:02d}")

    assert len(search_patients("Many")) == 20


def returns_nothing_when_the_patient_is_inactive_or_not_a_patient() -> None:
    gone = make("User", is_active=False)
    staff = make("User", role="CLINICIAN")
    live = make("User")

    assert active_patient(gone.pk) is None and active_patient(staff.pk) is None
    assert active_patient(None) is None
    assert active_patient(live.pk) == live
