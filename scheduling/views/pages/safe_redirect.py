"""The sign-in `next` parameter may only ever lead to a local path."""

from django.utils.http import url_has_allowed_host_and_scheme

FIRST_PRINTABLE = 32
DELETE_CHARACTER = 127


def local_path_or_home(candidate: str, home: str) -> str:
    """Browsers read `//host` and `/\\host` as another site, so both are refused with controls."""
    has_control = any(
        ord(char) < FIRST_PRINTABLE or ord(char) == DELETE_CHARACTER for char in candidate
    )
    is_local = (
        candidate.startswith("/")
        and not candidate.startswith("//")
        and "\\" not in candidate
        and not has_control
        and url_has_allowed_host_and_scheme(candidate, allowed_hosts=None)
    )
    return candidate if is_local else home
