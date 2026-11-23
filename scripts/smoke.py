import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.client import HTTPException
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

BASE_URL = "http://127.0.0.1:8000"
MAIL_BASE_URL = "http://127.0.0.1:8025"

HTTP_OK = 200
HTTP_CREATED = 201
REQUEST_TIMEOUT_SECONDS = 10
# Inside the 31 days one slot query may span.
SEARCH_DAYS = 14
# Past the 24 hour window in which a patient may cancel online (drlibre-specs.md 5.3).
SEARCH_LEAD_HOURS = 25
SMOKE_FULL_NAME = "Smoke Test"
SMOKE_DATE_OF_BIRTH = "1990-01-01"
SMOKE_CANCELLATION_REASON = "Smoke test cancellation"
PROVIDER_LINK = re.compile(r'href="/providers/([^"/?]+)')
BOOKING_CODE = re.compile(r"booking code is (\d{6})\b")

JsonBody = dict[str, object] | None


@dataclass(frozen=True)
class Reply:
    status: int
    body: str


# fetch(method, url, json_body) answers the stack; a refused connection raises SmokeFailure.
Fetch = Callable[[str, str, JsonBody], Reply]


@dataclass
class Journey:
    """What one smoke run learns on the way: each step reads what the earlier ones stored."""

    fetch: Fetch
    email: str = field(default_factory=lambda: f"smoke-{uuid4().hex}@example.test")
    provider_id: str = ""
    hold_id: str = ""
    code: str = ""
    appointment_id: str = ""


# Steps take no arguments: main() binds the journey into each one.
Step = tuple[str, Callable[[], None]]


class SmokeFailure(Exception):  # noqa: N818 - the test suite imports this name
    """A smoke step found the running stack in the wrong state."""


def run_steps(steps: list[Step]) -> int:
    for step_name, step in steps:
        try:
            step()
        except SmokeFailure as failure:
            print(f"Smoke step failed: {step_name}: {failure}", file=sys.stderr)
            return 1
    return 0


def make_fetch() -> Fetch:
    """Keeps cookies between steps, as a browser does: the verified code sets the session."""
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def fetch(method: str, url: str, json_body: JsonBody) -> Reply:
        data = None if json_body is None else json.dumps(json_body).encode()
        headers = {} if data is None else {"Content-Type": "application/json"}
        # S310: every URL is built from BASE_URL or MAIL_BASE_URL, both http on 127.0.0.1.
        request = Request(url, data=data, method=method, headers=headers)  # noqa: S310
        try:
            try:
                with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as answer:
                    return Reply(answer.status, answer.read().decode(errors="replace"))
            except HTTPError as refusal:
                return Reply(refusal.code, refusal.read().decode(errors="replace"))
        except (OSError, HTTPException) as failure:
            raise SmokeFailure(f"no answer from {url}: {failure}") from None

    return fetch


def _refusal_detail(body: str) -> str:
    """The error code and violated rules a refusal names, or nothing if it names none."""
    try:
        parsed: object = json.loads(body)
    except json.JSONDecodeError:
        return ""
    error = parsed.get("error") if isinstance(parsed, dict) else None
    if not isinstance(error, dict) or not isinstance(error.get("code"), str):
        return ""
    detail = f": {error['code']}"
    details = error.get("details")
    rules = details.get("violated_rules") if isinstance(details, dict) else None
    if not isinstance(rules, list):
        return detail
    named_rules = [rule for rule in rules if isinstance(rule, str)]
    if named_rules:
        detail += "; violated rules: " + ", ".join(named_rules)
    return detail


def _expect_status(answer: Reply, wanted_status: int, step_label: str) -> None:
    if answer.status != wanted_status:
        detail = _refusal_detail(answer.body)
        raise SmokeFailure(f"{step_label} answered {answer.status}, wanted {wanted_status}{detail}")


def _object_of(answer: Reply, wanted_status: int, step_label: str) -> dict[str, object]:
    _expect_status(answer, wanted_status, step_label)
    try:
        parsed: object = json.loads(answer.body)
    except json.JSONDecodeError:
        raise SmokeFailure(f"{step_label} body is not JSON") from None
    if not isinstance(parsed, dict):
        raise SmokeFailure(f"{step_label} body is not a JSON object")
    return parsed


def _objects_under(body: dict[str, object], key: str, step_label: str) -> list[dict[str, object]]:
    items = body.get(key)
    if not isinstance(items, list):
        raise SmokeFailure(f"{step_label} has no {key} list")
    return [item for item in items if isinstance(item, dict)]


def _text_under(body: dict[str, object], key: str, step_label: str) -> str:
    value = body.get(key)
    if not isinstance(value, str):
        raise SmokeFailure(f"{step_label} has no text {key}")
    return value


def health_step(journey: Journey) -> None:
    body = _object_of(journey.fetch("GET", f"{BASE_URL}/api/v1/health", None), HTTP_OK, "health")
    if body.get("status") != "ok":
        raise SmokeFailure(f"health reports {body.get('status')!r}, wanted 'ok'")


def start_page_step(journey: Journey) -> None:
    answer = journey.fetch("GET", f"{BASE_URL}/", None)
    _expect_status(answer, HTTP_OK, "start page")
    found = PROVIDER_LINK.search(answer.body)
    if found is None:
        raise SmokeFailure("start page links no provider")
    journey.provider_id = found.group(1)


def _instant(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _first_free_start(journey: Journey, appointment_type_id: str) -> str:
    start = datetime.now(UTC) + timedelta(hours=SEARCH_LEAD_HOURS)
    window = {
        "appointment_type_id": appointment_type_id,
        "from": _instant(start),
        "to": _instant(start + timedelta(days=SEARCH_DAYS)),
    }
    url = f"{BASE_URL}/api/v1/slots?{urlencode(window)}"
    listing = _object_of(journey.fetch("GET", url, None), HTTP_OK, "slots")
    free = _objects_under(listing, "slots", "slots")
    if not free:
        raise SmokeFailure(f"no free slot in the next {SEARCH_DAYS} days")
    return _text_under(free[0], "starts_at", "slot")


def hold_step(journey: Journey) -> None:
    provider_url = f"{BASE_URL}/api/v1/providers/{journey.provider_id}"
    provider = _object_of(journey.fetch("GET", provider_url, None), HTTP_OK, "provider")
    offered = _objects_under(provider, "appointment_types", "provider")
    if not offered:
        raise SmokeFailure("provider offers no appointment type")
    appointment_type_id = _text_under(offered[0], "id", "provider")
    booking = {
        "appointment_type_id": appointment_type_id,
        "starts_at": _first_free_start(journey, appointment_type_id),
        "full_name": SMOKE_FULL_NAME,
        "date_of_birth": SMOKE_DATE_OF_BIRTH,
        "email": journey.email,
        "terms_accepted": True,
    }
    hold_url = f"{BASE_URL}/api/v1/booking/holds"
    held = _object_of(journey.fetch("POST", hold_url, booking), HTTP_CREATED, "hold")
    journey.hold_id = _text_under(held, "id", "hold")


def code_step(journey: Journey) -> None:
    inbox_url = f"{MAIL_BASE_URL}/api/Messages?skip=0&take=1"
    inbox = _object_of(journey.fetch("GET", inbox_url, None), HTTP_OK, "mail inbox")
    newest = _objects_under(inbox, "results", "mail inbox")
    if not newest:
        raise SmokeFailure("mail inbox holds no message")
    message_id = _text_under(newest[0], "id", "mail inbox")
    text = journey.fetch("GET", f"{MAIL_BASE_URL}/api/Messages/{message_id}/plaintext", None)
    _expect_status(text, HTTP_OK, "mail message")
    found = BOOKING_CODE.search(text.body)
    if found is None:
        raise SmokeFailure("newest mail carries no booking code")
    journey.code = found.group(1)


def confirm_step(journey: Journey) -> None:
    verify_url = f"{BASE_URL}/api/v1/booking/holds/{journey.hold_id}/verify"
    verify_body: dict[str, object] = {"code": journey.code}
    confirmed = _object_of(
        journey.fetch("POST", verify_url, verify_body), HTTP_CREATED, "code check"
    )
    journey.appointment_id = _text_under(confirmed, "id", "code check")
    listing_url = f"{BASE_URL}/api/v1/appointments"
    listed = _object_of(journey.fetch("GET", listing_url, None), HTTP_OK, "appointment list")
    listed_ids = [item.get("id") for item in _objects_under(listed, "results", "appointments")]
    if journey.appointment_id not in listed_ids:
        raise SmokeFailure("the new patient's appointment is not listed")


def cancel_step(journey: Journey) -> None:
    cancel_url = f"{BASE_URL}/api/v1/appointments/{journey.appointment_id}/cancel"
    cancel_body: dict[str, object] = {"reason": SMOKE_CANCELLATION_REASON}
    cancelled = _object_of(journey.fetch("POST", cancel_url, cancel_body), HTTP_OK, "cancel")
    if cancelled.get("status") != "CANCELLED":
        raise SmokeFailure(f"appointment is {cancelled.get('status')!r}, wanted 'CANCELLED'")


def make_steps(fetch: Fetch) -> list[Step]:
    journey = Journey(fetch=fetch)
    return [
        ("health", lambda: health_step(journey)),
        ("start page", lambda: start_page_step(journey)),
        ("hold", lambda: hold_step(journey)),
        ("code", lambda: code_step(journey)),
        ("confirm", lambda: confirm_step(journey)),
        ("cancel", lambda: cancel_step(journey)),
    ]


def main() -> int:
    return run_steps(make_steps(make_fetch()))


if __name__ == "__main__":
    sys.exit(main())
