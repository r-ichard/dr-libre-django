"""Section 14: a test sees the next difference between the test client and the server.
These requests cross a socket to Django's WSGIServer, the class runserver uses."""

import socket
from http.client import HTTPConnection, HTTPResponse
from typing import Protocol

import pytest

from scheduling.views.fhir_test_support import token_of

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


def _raw_request(live_server: _Server, request_bytes: bytes) -> tuple[int, bytes]:
    host, port = live_server.url.removeprefix("http://").split(":")
    with socket.create_connection((host, int(port)), timeout=10) as connection:
        connection.sendall(request_bytes)
        received = b""
        while chunk := connection.recv(4096):
            received += chunk
    head, _separator, body = received.partition(b"\r\n\r\n")
    return int(head.split(b" ", 2)[1]), body


def _bare_request(method: str, path: str, host: str, credential: str) -> bytes:
    lines = [f"{method} {path} HTTP/1.1", f"Host: {host}", credential, "Connection: close"]
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


def returns_no_400_and_no_415_when_a_fhir_write_has_no_content_length_over_a_raw_socket(
    live_server: _Server, committed_rows: None
) -> None:
    token = token_of(role="ADMIN")
    host = live_server.url.removeprefix("http://")
    schedule = "00000000-0000-4000-8000-000000000000"

    status, _body = _raw_request(
        live_server,
        _bare_request(
            "DELETE", f"/fhir/Schedule/{schedule}", host, f"Authorization: Bearer {token}"
        ),
    )

    assert status not in (400, 415)


def returns_no_400_when_logout_has_no_content_length_over_a_raw_socket(
    live_server: _Server, committed_rows: None
) -> None:
    host = live_server.url.removeprefix("http://")

    status, _body = _raw_request(
        live_server, _bare_request("POST", "/api/v1/auth/logout", host, "Cookie: a=b")
    )

    assert status != 400


def returns_415_when_a_fhir_text_plain_body_arrives_over_a_raw_socket(
    live_server: _Server, committed_rows: None
) -> None:
    token = token_of(role="ADMIN")
    host = live_server.url.removeprefix("http://")
    head = (
        f"POST /fhir/Appointment HTTP/1.1\r\nHost: {host}\r\nAuthorization: Bearer {token}\r\n"
        "Content-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
    )

    status, body = _raw_request(live_server, head.encode())

    assert (status, b"OperationOutcome" in body) == (415, True)
