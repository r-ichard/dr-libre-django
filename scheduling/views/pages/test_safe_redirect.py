"""Task 05a: the sign-in `next` parameter may only ever lead to a local path."""

import pytest

HOME = "/patient/"


def _resolve(candidate: str) -> str:
    from scheduling.views.pages.safe_redirect import local_path_or_home

    return local_path_or_home(candidate, HOME)


@pytest.mark.parametrize(
    "candidate",
    [
        "https://evil.test/x",
        "http://evil.test",
        "//evil.test",
        "/\\evil.test",
        "\\\\evil.test",
        "javascript:alert(1)",
        "clinician/",
        "",
        "/clinician/\nSet-Cookie: a=b",
        "/clinician/\r",
        "/\tevil.test",
    ],
)
def returns_home_when_next_is_not_a_local_path(candidate: str) -> None:
    assert _resolve(candidate) == HOME


def returns_path_when_next_is_a_local_path() -> None:
    assert _resolve("/clinician/") == "/clinician/"


def returns_path_with_query_when_next_is_local() -> None:
    assert _resolve("/admin-console/?tab=1") == "/admin-console/?tab=1"
