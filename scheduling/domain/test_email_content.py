from dataclasses import replace
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from scheduling.domain.email_content import EmailSubject, patient_email

SUBJECT = EmailSubject(
    title="Appointment cancelled",
    starts_at=datetime(2030, 7, 1, 7, 5, tzinfo=UTC),
    time_zone=ZoneInfo("Europe/Berlin"),
    hospital_name="Riverside Hospital",
    provider_name="Dr Ada Byron",
    sign_in_url="https://drlibre.example/sign-in",
)


def returns_title_as_subject_and_first_line_when_building_the_email() -> None:
    text = patient_email(SUBJECT)

    assert text.subject == "Appointment cancelled"
    assert text.body.splitlines()[0] == "Appointment cancelled."


def returns_local_time_with_zone_name_when_the_zone_is_ahead_of_utc() -> None:
    body = patient_email(SUBJECT).body

    assert "When: 2030-07-01 at 09:05 (Europe/Berlin)" in body


def returns_date_of_the_local_day_when_local_time_crosses_midnight() -> None:
    late = replace(SUBJECT, starts_at=datetime(2030, 7, 1, 22, 30, tzinfo=UTC))

    assert "When: 2030-07-02 at 00:30 (Europe/Berlin)" in patient_email(late).body


def returns_hospital_provider_and_sign_in_link_on_their_own_lines() -> None:
    lines = patient_email(SUBJECT).body.splitlines()

    assert "Where: Riverside Hospital" in lines
    assert "Provider: Dr Ada Byron" in lines
    assert lines[-1] == "Sign in to see your appointments: https://drlibre.example/sign-in"


def returns_blank_lines_between_title_details_and_sign_in_when_building_the_email() -> None:
    assert patient_email(SUBJECT).body == (
        "Appointment cancelled.\n"
        "\n"
        "When: 2030-07-01 at 09:05 (Europe/Berlin)\n"
        "Where: Riverside Hospital\n"
        "Provider: Dr Ada Byron\n"
        "\n"
        "Sign in to see your appointments: https://drlibre.example/sign-in"
    )


def returns_title_and_sign_in_link_only_when_the_notification_has_no_appointment() -> None:
    bare = EmailSubject(title="A slot is free", sign_in_url="https://drlibre.example/sign-in")

    assert patient_email(bare).body == (
        "A slot is free.\n\nSign in to see your appointments: https://drlibre.example/sign-in"
    )


def returns_only_the_lines_whose_value_is_present_when_the_appointment_is_partly_known() -> None:
    partial = EmailSubject(
        title="Appointment booked",
        hospital_name="Riverside Hospital",
        sign_in_url="https://drlibre.example/sign-in",
    )

    assert patient_email(partial).body == (
        "Appointment booked.\n"
        "\n"
        "Where: Riverside Hospital\n"
        "\n"
        "Sign in to see your appointments: https://drlibre.example/sign-in"
    )


def returns_code_expiry_and_no_link_when_code_email_is_built() -> None:
    from scheduling.domain.email_content import verification_code_email  # noqa: PLC0415

    text = verification_code_email("042917", 10)

    assert "042917" in text.body
    assert "10 minutes" in text.body
    assert "http" not in text.body
    assert "042917" not in text.subject


def returns_exact_subject_and_body_when_code_email_is_built() -> None:
    from scheduling.domain.email_content import verification_code_email  # noqa: PLC0415

    text = verification_code_email("042917", 10)

    assert text.subject == "Your DrLibre booking code"
    assert text.body == (
        "Your DrLibre booking code is 042917.\n"
        "\n"
        "It is valid for 10 minutes. Enter it on the booking page to finish your booking.\n"
        "\n"
        "If you did not ask for this code, ignore this message."
    )


def returns_link_lifetime_and_single_use_when_sign_in_link_email_is_built() -> None:
    from scheduling.domain.email_content import sign_in_link_email  # noqa: PLC0415

    text = sign_in_link_email("https://drlibre.example/sign-in/link?token=abc", 15)

    assert "https://drlibre.example/sign-in/link?token=abc" in text.body.splitlines()
    assert "15 minutes" in text.body
    assert "only once" in text.body
    assert "abc" not in text.subject


def returns_no_signing_link_when_other_emails_are_built() -> None:
    from scheduling.domain.email_content import verification_code_email  # noqa: PLC0415

    assert "token=" not in patient_email(SUBJECT).body
    assert "token=" not in verification_code_email("042917", 10).body


def returns_exact_subject_and_body_when_sign_in_link_email_is_built() -> None:
    from scheduling.domain.email_content import sign_in_link_email  # noqa: PLC0415

    text = sign_in_link_email("https://drlibre.example/sign-in/link?token=abc", 15)

    assert text.subject == "Your DrLibre sign-in link"
    assert text.body == (
        "Use this link to sign in to DrLibre:\n"
        "\n"
        "https://drlibre.example/sign-in/link?token=abc\n"
        "\n"
        "The link is valid for 15 minutes and works only once. Opening it shows a page with a "
        "Continue button; you are signed in when you press it.\n"
        "\n"
        "If you did not ask for this link, ignore this message."
    )
