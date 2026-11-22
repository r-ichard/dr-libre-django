"""Task 26a2 item 2: the next difference between the test client and the server is seen by a test.
These requests cross a socket to Django's WSGIServer, the class runserver uses."""

from http.client import HTTPConnection, HTTPResponse
from typing import Protocol

import pytest

pytestmark = pytest.mark.django_db(transaction=True)


class _Server(Protocol):
    url: str


def _post(
    live_server: _Server, path: str, body: bytes | None, headers: dict[str, str]
) -> tuple[HTTPResponse, bytes]:
    host = live_server.url.removeprefix("http://")
    connection = HTTPConnection(host, timeout=10)
    try:
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        return response, response.read()
    finally:
        connection.close()


def returns_logout_answer_when_post_has_no_body_and_no_type_over_a_socket(
    live_server: _Server, committed_rows: None
) -> None:
    response, body = _post(live_server, "/api/v1/auth/logout", None, {})

    assert (response.status, b"not readable" in body) in [(200, False), (204, False), (401, False)]


def returns_invalid_input_when_text_plain_body_is_posted_over_a_socket(
    live_server: _Server, committed_rows: None
) -> None:
    response, body = _post(
        live_server, "/api/v1/auth/login", b'{"email": "a@b.test"}', {"Content-Type": "text/plain"}
    )

    assert response.status == 400
    assert b"invalid_input" in body
    assert b"body" in body
