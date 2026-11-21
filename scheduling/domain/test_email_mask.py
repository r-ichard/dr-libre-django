def returns_first_letter_and_domain_when_email_is_masked() -> None:
    from scheduling.domain.email_mask import mask_email

    assert mask_email("pat.smith@example.test") == "p***@example.test"


def returns_stars_and_domain_when_local_part_is_one_letter() -> None:
    from scheduling.domain.email_mask import mask_email

    assert mask_email("p@example.test") == "***@example.test"


def returns_first_letter_when_local_part_has_two_letters() -> None:
    from scheduling.domain.email_mask import mask_email

    assert mask_email("ab@example.test") == "a***@example.test"
