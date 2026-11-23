"""A specialty code maps to one vendored icon, a fallback otherwise."""


def returns_fallback_icon_when_specialty_code_is_unknown() -> None:
    from scheduling.domain.specialty_icons import FALLBACK_ICON, icon_file_for

    icon = icon_file_for("underwater-basket-weaving")

    assert icon == FALLBACK_ICON == "fallback.svg"


def returns_cardiology_icon_when_code_is_demo_cardiology() -> None:
    from scheduling.domain.specialty_icons import icon_file_for

    icon = icon_file_for("cardiology")

    assert icon == "cardiology.svg"
