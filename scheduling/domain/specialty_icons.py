"""Task 10a: a specialty maps to one vendored icon file, the fallback when it has none."""

FALLBACK_ICON = "fallback.svg"
VENDORED_CODES = frozenset(
    {"cardiology", "dermatology", "general-practice", "paediatrics", "orthopaedics"}
)


def icon_file_for(code: str) -> str:
    return f"{code}.svg" if code in VENDORED_CODES else FALLBACK_ICON
