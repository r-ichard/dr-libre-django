"""Task 26b item 3: the caller's address behind a counted number of trusted proxies."""

import importlib

REMOTE = "10.0.0.5"


def _caller_address(remote: str, forwarded: str, trusted: int) -> str:
    module = importlib.import_module("scheduling.domain.forwarded_address")
    return str(module.caller_address(remote, forwarded, trusted))


def returns_remote_address_when_no_proxy_is_trusted_and_header_is_set() -> None:
    assert _caller_address(REMOTE, "1.1.1.1, 2.2.2.2", 0) == REMOTE


def returns_rightmost_entry_when_one_proxy_is_trusted() -> None:
    assert _caller_address(REMOTE, "1.1.1.1, 2.2.2.2", 1) == "2.2.2.2"


def returns_second_from_right_when_two_proxies_are_trusted() -> None:
    assert _caller_address(REMOTE, "9.9.9.9, 1.1.1.1, 2.2.2.2", 2) == "1.1.1.1"


def returns_remote_address_when_header_has_fewer_entries_than_trusted_proxies() -> None:
    assert _caller_address(REMOTE, "2.2.2.2", 2) == REMOTE


def returns_remote_address_when_entry_is_not_an_address() -> None:
    assert _caller_address(REMOTE, "1.1.1.1, not-an-address", 1) == REMOTE


def returns_remote_address_when_header_is_empty() -> None:
    assert _caller_address(REMOTE, "", 1) == REMOTE


def returns_entry_without_surrounding_spaces_when_header_has_spaces() -> None:
    assert _caller_address(REMOTE, "1.1.1.1 ,  2.2.2.2  ", 1) == "2.2.2.2"


def returns_only_entry_when_header_has_exactly_as_many_entries_as_trusted_proxies() -> None:
    assert _caller_address(REMOTE, "2.2.2.2", 1) == "2.2.2.2"
    assert _caller_address(REMOTE, "1.1.1.1, 2.2.2.2", 2) == "1.1.1.1"
