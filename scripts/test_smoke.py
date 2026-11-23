import json
import socket
from collections.abc import Callable
from datetime import datetime, timedelta
from email.message import Message
from http.client import BadStatusLine, IncompleteRead
from io import BytesIO
from typing import NoReturn
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest

from scripts.smoke import (
    BASE_URL,
    MAIL_BASE_URL,
    SEARCH_DAYS,
    SMOKE_CANCELLATION_REASON,
    SMOKE_DATE_OF_BIRTH,
    SMOKE_FULL_NAME,
    Journey,
    JsonBody,
    Reply,
    SmokeFailure,
    Step,
    cancel_step,
    code_step,
    confirm_step,
    health_step,
    hold_step,
    make_fetch,
    make_steps,
    run_steps,
    start_page_step,
)

PROVIDER_ID = "6f1c2a3e-8b4d-4e5f-9a6b-7c8d9e0f1a2b"
APPOINTMENT_TYPE_ID = "1d2e3f40-5a6b-4c7d-8e9f-0a1b2c3d4e5f"
CLINICIAN_ID = "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
SLOT_START = "2026-11-30T09:00:00Z"
LATER_SLOT_START = "2026-11-30T10:00:00Z"
INSTANT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
HOLD_ID = "3c4d5e6f-7a8b-4c9d-8e0f-1a2b3c4d5e6f"
MESSAGE_ID = "b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e"
APPOINTMENT_ID = "e5f6a7b8-c9d0-4e1f-8a2b-3c4d5e6f7a8b"
CODE = "482913"


class FakeStack:
    """Answers by method and a fragment of the URL, and records every request it gets."""

    def __init__(self, answers: dict[tuple[str, str], Reply]) -> None:
        self._answers = answers
        self.sent: list[tuple[str, str, JsonBody]] = []

    def __call__(self, method: str, url: str, body: JsonBody) -> Reply:
        self.sent.append((method, url, body))
        for (wanted_method, fragment), reply in self._answers.items():
            if wanted_method == method and fragment in url:
                return reply
        return Reply(404, "")


def _json(value: object) -> str:
    return json.dumps(value)


HEALTH_ANSWER = Reply(200, _json({"status": "ok"}))
START_PAGE_ANSWER = Reply(200, f'<h2><a href="/providers/{PROVIDER_ID}">Dr Example</a></h2>')
PROVIDER_ANSWER = Reply(
    200,
    _json(
        {
            "appointment_types": [
                {"id": APPOINTMENT_TYPE_ID, "name": "Review", "duration_minutes": 30}
            ]
        }
    ),
)
SLOTS_ANSWER = Reply(
    200,
    _json(
        {
            "time_zone": "UTC",
            "slots": [
                {
                    "starts_at": SLOT_START,
                    "ends_at": "2026-11-30T09:30:00Z",
                    "clinician_ids": [CLINICIAN_ID],
                },
                {
                    "starts_at": LATER_SLOT_START,
                    "ends_at": "2026-11-30T10:30:00Z",
                    "clinician_ids": [CLINICIAN_ID],
                },
            ],
        }
    ),
)
HOLD_ANSWER = Reply(201, _json({"id": HOLD_ID, "starts_at": SLOT_START}))
INBOX_ANSWER = Reply(
    200, _json({"results": [{"id": MESSAGE_ID, "subject": "Your DrLibre booking code"}]})
)
MESSAGE_ANSWER = Reply(200, f"Your DrLibre booking code is {CODE}.\n\nIt is valid for 10 minutes.")
VERIFY_ANSWER = Reply(201, _json({"id": APPOINTMENT_ID, "status": "BOOKED"}))
LISTED_ANSWER = Reply(
    200, _json({"count": 1, "results": [{"id": APPOINTMENT_ID, "status": "BOOKED"}]})
)
CANCELLED_ANSWER = Reply(200, _json({"id": APPOINTMENT_ID, "status": "CANCELLED"}))


def _failing_step(reason: str) -> Callable[[], None]:
    def step() -> None:
        raise SmokeFailure(reason)

    return step


def returns_zero_and_prints_nothing_when_every_step_passes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    steps: list[Step] = [("one", lambda: None), ("two", lambda: None)]

    exit_code = run_steps(steps)

    assert exit_code == 0
    assert capsys.readouterr().err == ""


def returns_one_and_names_the_failing_step_when_a_step_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    steps: list[Step] = [("one", lambda: None), ("two", _failing_step("answered 500"))]

    exit_code = run_steps(steps)

    assert exit_code == 1
    assert capsys.readouterr().err == "Smoke step failed: two: answered 500\n"


def returns_one_without_running_later_steps_when_a_step_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    later_calls: list[str] = []
    steps: list[Step] = [
        ("one", _failing_step("refused")),
        ("two", lambda: later_calls.append("two")),
    ]

    run_steps(steps)

    assert later_calls == []
    assert capsys.readouterr().err == "Smoke step failed: one: refused\n"


def raises_unexpected_error_without_reporting_a_step(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def broken_step() -> None:
        raise RuntimeError("invariant broken")

    steps: list[Step] = [("one", broken_step)]

    with pytest.raises(RuntimeError, match="invariant broken"):
        run_steps(steps)
    assert capsys.readouterr().err == ""


def returns_nothing_when_health_answers_ok() -> None:
    stack = FakeStack({("GET", "/api/v1/health"): HEALTH_ANSWER})

    health_step(Journey(fetch=stack))

    assert stack.sent == [("GET", f"{BASE_URL}/api/v1/health", None)]


def raises_smoke_failure_when_health_status_is_not_ok() -> None:
    stack = FakeStack({("GET", "/api/v1/health"): Reply(200, _json({"status": "down"}))})

    with pytest.raises(SmokeFailure, match="health reports 'down'"):
        health_step(Journey(fetch=stack))


def raises_smoke_failure_when_health_answers_not_200() -> None:
    stack = FakeStack({("GET", "/api/v1/health"): Reply(503, _json({"status": "ok"}))})

    with pytest.raises(SmokeFailure, match="health answered 503"):
        health_step(Journey(fetch=stack))


def raises_smoke_failure_when_health_body_is_not_json() -> None:
    stack = FakeStack({("GET", "/api/v1/health"): Reply(200, "<html>maintenance</html>")})

    with pytest.raises(SmokeFailure, match="health body is not JSON"):
        health_step(Journey(fetch=stack))


def raises_smoke_failure_when_health_body_is_not_an_object() -> None:
    stack = FakeStack({("GET", "/api/v1/health"): Reply(200, _json(["ok"]))})

    with pytest.raises(SmokeFailure, match="health body is not a JSON object"):
        health_step(Journey(fetch=stack))


def raises_smoke_failure_without_traceback_when_stack_refuses_connection() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]

    with pytest.raises(SmokeFailure) as failure:
        make_fetch()("GET", f"http://127.0.0.1:{closed_port}/api/v1/health", None)

    assert "Traceback" not in str(failure.value)


def raises_smoke_failure_when_stack_answers_with_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    class GarbageOpener:
        def open(self, request: Request, timeout: float) -> NoReturn:
            raise BadStatusLine("NOT HTTP")

    monkeypatch.setattr("scripts.smoke.build_opener", lambda *handlers: GarbageOpener())

    with pytest.raises(SmokeFailure, match="no answer from"):
        make_fetch()("GET", f"{BASE_URL}/api/v1/health", None)


def raises_smoke_failure_when_refusal_body_cannot_be_read(monkeypatch: pytest.MonkeyPatch) -> None:
    class DroppedBody(BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            raise IncompleteRead(b"")

    class RefusingOpener:
        def open(self, request: Request, timeout: float) -> NoReturn:
            raise HTTPError(
                request.full_url, 500, "Internal Server Error", Message(), DroppedBody()
            )

    monkeypatch.setattr("scripts.smoke.build_opener", lambda *handlers: RefusingOpener())

    with pytest.raises(SmokeFailure, match="no answer from"):
        make_fetch()("GET", f"{BASE_URL}/api/v1/health", None)


def returns_loopback_urls_when_smoke_constants_are_read() -> None:
    assert BASE_URL.startswith("http://127.0.0.1:")
    assert MAIL_BASE_URL.startswith("http://127.0.0.1:")


def returns_nothing_when_start_page_links_a_provider() -> None:
    stack = FakeStack({("GET", BASE_URL + "/"): START_PAGE_ANSWER})
    journey = Journey(fetch=stack)

    start_page_step(journey)

    assert stack.sent == [("GET", f"{BASE_URL}/", None)]
    assert journey.provider_id == PROVIDER_ID


def raises_smoke_failure_when_start_page_lists_no_provider() -> None:
    stack = FakeStack({("GET", BASE_URL + "/"): Reply(200, "<p>No providers</p>")})

    with pytest.raises(SmokeFailure, match="links no provider"):
        start_page_step(Journey(fetch=stack))


def raises_smoke_failure_when_start_page_answers_not_200() -> None:
    stack = FakeStack({("GET", BASE_URL + "/"): Reply(500, START_PAGE_ANSWER.body)})

    with pytest.raises(SmokeFailure, match="start page answered 500"):
        start_page_step(Journey(fetch=stack))


def _hold_stack(hold: Reply, slots: Reply = SLOTS_ANSWER) -> FakeStack:
    return FakeStack(
        {
            ("GET", f"/api/v1/providers/{PROVIDER_ID}"): PROVIDER_ANSWER,
            ("GET", "/api/v1/slots"): slots,
            ("POST", "/api/v1/booking/holds"): hold,
        }
    )


def returns_hold_id_when_a_free_slot_is_held() -> None:
    journey = Journey(fetch=_hold_stack(HOLD_ANSWER), provider_id=PROVIDER_ID)

    hold_step(journey)

    assert journey.hold_id == HOLD_ID


def returns_hold_request_for_first_free_slot_when_holding() -> None:
    stack = _hold_stack(HOLD_ANSWER)
    journey = Journey(fetch=stack, provider_id=PROVIDER_ID)

    hold_step(journey)

    assert stack.sent[-1] == (
        "POST",
        f"{BASE_URL}/api/v1/booking/holds",
        {
            "appointment_type_id": APPOINTMENT_TYPE_ID,
            "starts_at": SLOT_START,
            "full_name": SMOKE_FULL_NAME,
            "date_of_birth": SMOKE_DATE_OF_BIRTH,
            "email": journey.email,
            "terms_accepted": True,
        },
    )


def returns_utc_search_window_of_search_days_when_holding() -> None:
    stack = _hold_stack(HOLD_ANSWER)

    hold_step(Journey(fetch=stack, provider_id=PROVIDER_ID))

    slots_url = next(url for _, url, _ in stack.sent if "/api/v1/slots" in url)
    window = parse_qs(urlsplit(slots_url).query)
    starts = datetime.strptime(window["from"][0], INSTANT_FORMAT)
    ends = datetime.strptime(window["to"][0], INSTANT_FORMAT)
    assert ends - starts == timedelta(days=SEARCH_DAYS)
    assert window["appointment_type_id"] == [APPOINTMENT_TYPE_ID]


def raises_smoke_failure_when_no_slot_is_free() -> None:
    stack = _hold_stack(HOLD_ANSWER, Reply(200, _json({"time_zone": "UTC", "slots": []})))

    with pytest.raises(SmokeFailure, match="no free slot"):
        hold_step(Journey(fetch=stack, provider_id=PROVIDER_ID))


def raises_smoke_failure_when_slot_listing_has_no_slots_list() -> None:
    stack = _hold_stack(HOLD_ANSWER, Reply(200, _json({"time_zone": "UTC"})))

    with pytest.raises(SmokeFailure, match="has no slots list"):
        hold_step(Journey(fetch=stack, provider_id=PROVIDER_ID))


def raises_smoke_failure_when_hold_is_refused() -> None:
    stack = _hold_stack(Reply(409, _json({"code": "conflict"})))

    with pytest.raises(SmokeFailure, match="hold answered 409"):
        hold_step(Journey(fetch=stack, provider_id=PROVIDER_ID))


def returns_booking_code_when_newest_message_carries_it() -> None:
    stack = FakeStack(
        {("GET", "/api/Messages?"): INBOX_ANSWER, ("GET", "/plaintext"): MESSAGE_ANSWER}
    )
    journey = Journey(fetch=stack)

    code_step(journey)

    assert journey.code == CODE


def raises_smoke_failure_when_inbox_has_no_message() -> None:
    stack = FakeStack({("GET", "/api/Messages?"): Reply(200, _json({"results": []}))})

    with pytest.raises(SmokeFailure, match="holds no message"):
        code_step(Journey(fetch=stack))


def raises_smoke_failure_when_message_has_no_booking_code() -> None:
    stack = FakeStack(
        {("GET", "/api/Messages?"): INBOX_ANSWER, ("GET", "/plaintext"): Reply(200, "Hello")}
    )

    with pytest.raises(SmokeFailure, match="carries no booking code"):
        code_step(Journey(fetch=stack))


def raises_smoke_failure_when_message_text_answers_not_200() -> None:
    stack = FakeStack(
        {
            ("GET", "/api/Messages?"): INBOX_ANSWER,
            ("GET", "/plaintext"): Reply(500, MESSAGE_ANSWER.body),
        }
    )

    with pytest.raises(SmokeFailure, match="mail message answered 500"):
        code_step(Journey(fetch=stack))


def returns_appointment_id_when_code_confirms_and_patient_sees_it() -> None:
    stack = FakeStack(
        {("POST", "/verify"): VERIFY_ANSWER, ("GET", "/api/v1/appointments"): LISTED_ANSWER}
    )
    journey = Journey(fetch=stack, hold_id=HOLD_ID, code=CODE)

    confirm_step(journey)

    assert stack.sent[0] == (
        "POST",
        f"{BASE_URL}/api/v1/booking/holds/{HOLD_ID}/verify",
        {"code": CODE},
    )
    assert journey.appointment_id == APPOINTMENT_ID


def raises_smoke_failure_when_code_is_refused() -> None:
    stack = FakeStack({("POST", "/verify"): Reply(400, _json({"code": "invalid_input"}))})

    with pytest.raises(SmokeFailure, match="code check answered 400"):
        confirm_step(Journey(fetch=stack, hold_id=HOLD_ID, code=CODE))


def raises_smoke_failure_when_appointment_is_not_listed() -> None:
    stack = FakeStack(
        {
            ("POST", "/verify"): VERIFY_ANSWER,
            ("GET", "/api/v1/appointments"): Reply(200, _json({"count": 0, "results": []})),
        }
    )

    with pytest.raises(SmokeFailure, match="not listed"):
        confirm_step(Journey(fetch=stack, hold_id=HOLD_ID, code=CODE))


def returns_cancel_request_for_booked_appointment_when_patient_cancels() -> None:
    stack = FakeStack({("POST", "/cancel"): CANCELLED_ANSWER})

    cancel_step(Journey(fetch=stack, appointment_id=APPOINTMENT_ID))

    assert stack.sent[0] == (
        "POST",
        f"{BASE_URL}/api/v1/appointments/{APPOINTMENT_ID}/cancel",
        {"reason": SMOKE_CANCELLATION_REASON},
    )


def raises_smoke_failure_when_appointment_is_not_cancelled() -> None:
    stack = FakeStack({("POST", "/cancel"): Reply(200, _json({"status": "BOOKED"}))})

    with pytest.raises(SmokeFailure, match="wanted 'CANCELLED'"):
        cancel_step(Journey(fetch=stack, appointment_id=APPOINTMENT_ID))


def raises_smoke_failure_when_cancel_is_refused() -> None:
    stack = FakeStack({("POST", "/cancel"): Reply(409, _json({"code": "conflict"}))})

    with pytest.raises(SmokeFailure, match="cancel answered 409"):
        cancel_step(Journey(fetch=stack, appointment_id=APPOINTMENT_ID))


def _stack_of(replaced: dict[str, Reply]) -> FakeStack:
    """The stack's answers, in the order FakeStack matches them; replaced names win."""
    rows = [
        ("health", "GET", "/api/v1/health", HEALTH_ANSWER),
        ("verify", "POST", "/verify", VERIFY_ANSWER),
        ("cancel", "POST", "/cancel", CANCELLED_ANSWER),
        ("hold", "POST", "/api/v1/booking/holds", HOLD_ANSWER),
        ("provider", "GET", f"/api/v1/providers/{PROVIDER_ID}", PROVIDER_ANSWER),
        ("slots", "GET", "/api/v1/slots", SLOTS_ANSWER),
        ("listed", "GET", "/api/v1/appointments", LISTED_ANSWER),
        ("inbox", "GET", "/api/Messages?", INBOX_ANSWER),
        ("message", "GET", "/plaintext", MESSAGE_ANSWER),
        ("start", "GET", f"{BASE_URL}/", START_PAGE_ANSWER),
    ]
    return FakeStack(
        {(method, fragment): replaced.get(name, reply) for name, method, fragment, reply in rows}
    )


def returns_zero_and_prints_nothing_when_every_step_answers_as_the_stack_does(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_steps(make_steps(_stack_of({})))

    assert (exit_code, capsys.readouterr().err) == (0, "")


@pytest.mark.parametrize(
    ("step_name", "broken_answer", "wrong_answer"),
    [
        ("health", "health", Reply(200, _json({"status": "down"}))),
        ("start page", "start", Reply(200, "<p>No providers</p>")),
        ("hold", "hold", Reply(409, _json({"code": "conflict"}))),
        ("code", "inbox", Reply(200, _json({"results": []}))),
        ("confirm", "verify", Reply(400, _json({"code": "invalid_input"}))),
        ("cancel", "cancel", Reply(200, _json({"status": "BOOKED"}))),
    ],
)
def returns_one_naming_the_step_when_its_answer_is_wrong(
    step_name: str,
    broken_answer: str,
    wrong_answer: Reply,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_steps(make_steps(_stack_of({broken_answer: wrong_answer})))

    assert exit_code == 1
    assert capsys.readouterr().err.startswith(f"Smoke step failed: {step_name}: ")


def raises_smoke_failure_when_slot_listing_is_not_json() -> None:
    stack = _hold_stack(HOLD_ANSWER, Reply(200, "<html>maintenance</html>"))

    with pytest.raises(SmokeFailure, match="slots body is not JSON"):
        hold_step(Journey(fetch=stack, provider_id=PROVIDER_ID))
