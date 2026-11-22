"""Task 27d, slice 1, spec 15.5: a search answers the set its parameters name: dates by their
FHIR prefix, a comma as "either", a closed code list as 400, a NUL byte as 400."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from django.db.models import Model
from hypothesis import given, settings, strategies

from scheduling.domain.fhir_audit_action import EXPLICIT_CODES, audit_action_code
from scheduling.domain.fhir_declaration import FHIR_RESOURCES, ParameterKind
from scheduling.models import User
from scheduling.models.builders import make
from scheduling.views.fhir_test_support import get, token_of

pytestmark = pytest.mark.django_db

BOUND = datetime(2026, 11, 24, 0, 0, tzinfo=UTC)
OFFSETS = {
    "a": -timedelta(days=1),
    "b": -timedelta(hours=12),
    "c": -timedelta(seconds=1),
    "d": timedelta(0),
    "e": timedelta(seconds=1),
    "f": timedelta(hours=12),
    "g": timedelta(days=1),
}
BOUND_TEXT = "2026-11-24T00:00:00Z"


def _appointment(moment: datetime, admin: User) -> Model:
    return make("Appointment", starts_at=moment, ends_at=moment + timedelta(minutes=30))


def _communication(moment: datetime, admin: User) -> Model:
    return make("Notification", recipient=admin, created_at=moment)


def _audit(moment: datetime, admin: User) -> Model:
    return make("AuditLogEntry", actor=admin, created_at=moment)


TYPES: dict[str, tuple[Callable[[datetime, User], Model], str]] = {
    "Appointment": (_appointment, "date"),
    "Communication": (_communication, "sent"),
    "AuditEvent": (_audit, "date"),
}


def _admin() -> tuple[User, str]:
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    return admin, token_of(admin)


def _ids_found(path: str, token: str) -> set[str]:
    response = get(path + "&_count=100", token)
    assert response.status_code == 200, response.content
    return {entry["resource"]["id"] for entry in response.json().get("entry", [])}


def _rows(kind: str, moments: dict[str, datetime]) -> tuple[str, dict[str, str]]:
    admin, token = _admin()
    build, _ = TYPES[kind]
    return token, {letter: str(build(moment, admin).pk) for letter, moment in moments.items()}


def _names(found: set[str], ids: dict[str, str]) -> str:
    return "".join(sorted(letter for letter, pk in ids.items() if pk in found))


@pytest.mark.parametrize("kind", list(TYPES))
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (f"lt{BOUND_TEXT}", "abc"),
        (f"le{BOUND_TEXT}", "abcd"),
        (f"eq{BOUND_TEXT}", "d"),
        (BOUND_TEXT, "d"),
        (f"ge{BOUND_TEXT}", "defg"),
        (f"gt{BOUND_TEXT}", "efg"),
        ("lt2026-11-24T01:00:00%2B01:00", "abc"),
        ("ge2026-11-24T01:00:00%2B01:00", "defg"),
        ("2026-11-24", "def"),
        ("eq2026-11-23", "abc"),
        ("lt2026-11-24", "abc"),
        ("ge2026-11-24", "defg"),
        ("gt2026-11-24", "g"),
        ("le2026-11-24", "abcdef"),
    ],
)
def returns_the_rows_the_prefix_names_when_bound_has_a_given_precision(
    kind: str, value: str, expected: str
) -> None:
    token, ids = _rows(kind, {letter: BOUND + shift for letter, shift in OFFSETS.items()})
    parameter = TYPES[kind][1]

    found = _ids_found(f"/fhir/{kind}?{parameter}={value}", token)

    assert _names(found, ids) == expected


@pytest.mark.parametrize("kind", list(TYPES))
def returns_each_day_its_own_rows_when_a_calendar_is_read_day_by_day(kind: str) -> None:
    moments = {
        "a": datetime(2026, 11, 23, 12, tzinfo=UTC),
        "b": datetime(2026, 11, 23, 21, tzinfo=UTC),
        "c": datetime(2026, 11, 24, 9, tzinfo=UTC),
        "d": datetime(2026, 11, 24, 23, tzinfo=UTC),
    }
    token, ids = _rows(kind, moments)
    parameter = TYPES[kind][1]
    base = f"/fhir/{kind}?{parameter}="

    day_23 = _ids_found(base + "2026-11-23", token)
    day_24 = _ids_found(base + "2026-11-24", token)
    ranged = _ids_found(f"{base}ge2026-11-23&{parameter}=lt2026-11-24", token)
    until = _ids_found(base + "le2026-11-23T23:59:59Z", token)
    after = _ids_found(base + "gt2026-11-23T20:00:00Z", token)

    assert _names(day_23, ids) == "ab"
    assert _names(day_24, ids) == "cd"
    assert _names(ranged, ids) == "ab"
    assert _names(until, ids) == "ab"
    assert _names(after, ids) == "bcd"


@pytest.mark.parametrize("kind", list(TYPES))
@pytest.mark.parametrize("value", ["ne2026-11-24", "sa2026-11-24", "eb2026-11-24", "ap2026-11-24"])
def returns_400_naming_date_when_prefix_is_not_served(kind: str, value: str) -> None:
    _, token = _admin()
    parameter = TYPES[kind][1]

    response = get(f"/fhir/{kind}?{parameter}={value}", token)

    assert response.status_code == 400
    assert parameter in str(response.json()["issue"])


@pytest.mark.parametrize("kind", list(TYPES))
def returns_400_when_a_date_has_a_comma(kind: str) -> None:
    _, token = _admin()
    parameter = TYPES[kind][1]

    response = get(f"/fhir/{kind}?{parameter}=2026-11-23,2026-11-24", token)

    assert response.status_code == 400


@pytest.mark.parametrize("kind", list(TYPES))
@settings(max_examples=15, deadline=None)
@given(
    shift=strategies.integers(min_value=-90_000, max_value=90_000),
)
def returns_every_row_once_when_lt_and_ge_share_a_bound(kind: str, shift: int) -> None:
    from django.db import transaction

    with transaction.atomic():
        moments = {
            letter: BOUND + timedelta(seconds=seconds)
            for letter, seconds in zip("abcdef", (-86_400, -3_600, -1, 0, 1, 43_200), strict=True)
        }
        token, ids = _rows(kind, moments)
        parameter = TYPES[kind][1]
        bound = (BOUND + timedelta(seconds=shift)).strftime("%Y-%m-%dT%H:%M:%SZ")

        below = _ids_found(f"/fhir/{kind}?{parameter}=lt{bound}", token)
        above = _ids_found(f"/fhir/{kind}?{parameter}=ge{bound}", token)

        assert not below & above
        assert set(ids.values()) <= below | above
        transaction.set_rollback(True)


@pytest.mark.parametrize("kind", list(TYPES))
def returns_the_day_when_ge_the_day_and_lt_the_next_are_combined(kind: str) -> None:
    moments = {"a": BOUND - timedelta(seconds=1), "b": BOUND, "c": BOUND + timedelta(hours=23)}
    moments["d"] = BOUND + timedelta(days=1)
    token, ids = _rows(kind, moments)
    parameter = TYPES[kind][1]
    base = f"/fhir/{kind}?{parameter}="

    both = _ids_found(f"{base}ge2026-11-24&{parameter}=lt2026-11-25", token)
    equal = _ids_found(f"{base}eq2026-11-24", token)

    assert _names(both, ids) == "bc"
    assert both == equal


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2026-11-24", "b"), ("lt2026-11-24", "a"), ("gt2026-11-24", "c"), ("ge2026-11-24", "bc")],
)
def returns_the_patients_born_by_day_when_birthdate_is_searched(value: str, expected: str) -> None:
    _, token = _admin()
    born = {"a": date(2026, 11, 23), "b": date(2026, 11, 24), "c": date(2026, 11, 25)}
    ids = {
        letter: str(make("User", role="PATIENT", date_of_birth=day).pk)
        for letter, day in born.items()
    }

    found = _ids_found(f"/fhir/Patient?birthdate={value}", token)

    assert _names(found, ids) == expected


def _string_parameters() -> list[tuple[str, str]]:
    return [
        (item.type, parameter.name)
        for item in FHIR_RESOURCES
        for parameter in item.parameters
        if parameter.kind is not ParameterKind.FLAG
    ]


@pytest.mark.parametrize(("kind", "name"), _string_parameters())
@pytest.mark.parametrize("who", ["anonymous", "admin"])
def returns_400_naming_the_parameter_when_value_has_a_nul_byte(
    kind: str, name: str, who: str
) -> None:
    token = None if who == "anonymous" else token_of(role="ADMIN")

    response = get(f"/fhir/{kind}?{name}=a%00b", token)

    assert response.status_code in {400, 401}
    if response.status_code == 400:
        assert name in str(response.json()["issue"])


@pytest.mark.parametrize("name", ["_sort", "_include", "_count", "_offset", "_format"])
def returns_no_500_when_a_common_parameter_has_a_nul_byte(name: str) -> None:
    response = get(f"/fhir/Organization?{name}=a%00b", token_of(role="ADMIN"))

    assert response.status_code == 400


def returns_either_when_status_has_a_comma() -> None:
    _, token = _admin()
    booked = make("Appointment", status="BOOKED")
    cancelled = make(
        "Appointment",
        status="CANCELLED",
        cancelled_at=datetime(2030, 1, 1, tzinfo=UTC),
        cancellation_reason="Patient asked",
    )
    make("Appointment", status="COMPLETED")

    found = _ids_found("/fhir/Appointment?status=booked,cancelled", token)

    assert found == {str(booked.pk), str(cancelled.pk)}


def returns_either_when_type_has_a_comma() -> None:
    _, token = _admin()
    hospital = make("Hospital")
    department = make("Department")

    found = _ids_found("/fhir/Organization?type=prov,dept", token)

    assert {str(hospital.pk), str(department.pk)} <= found


def returns_400_listing_the_codes_when_status_is_not_a_code() -> None:
    _, token = _admin()

    response = get("/fhir/Appointment?status=booked,nonsense", token)

    text = str(response.json()["issue"])
    assert response.status_code == 400
    assert "status" in text
    assert "booked" in text
    assert "cancelled" in text


def returns_the_events_showing_the_code_when_action_is_a_fhir_code() -> None:
    admin, token = _admin()
    created = make("AuditLogEntry", actor=admin, action="appointment.book")
    updated = make("AuditLogEntry", actor=admin, action="appointment.cancel")
    deleted = make("AuditLogEntry", actor=admin, action="time_off.delete")

    only_c = _ids_found("/fhir/AuditEvent?action=C", token)
    c_or_d = _ids_found("/fhir/AuditEvent?action=C,D", token)

    assert str(created.pk) in only_c
    assert not {str(updated.pk), str(deleted.pk)} & only_c
    assert {str(created.pk), str(deleted.pk)} <= c_or_d
    assert str(updated.pk) not in c_or_d


def returns_400_listing_the_codes_when_action_is_not_a_code() -> None:
    _, token = _admin()

    response = get("/fhir/AuditEvent?action=Z", token)

    assert response.status_code == 400
    assert "action" in str(response.json()["issue"])


@pytest.mark.parametrize("code", ["C", "R", "U", "D", "E"])
def returns_exactly_the_events_showing_the_code_when_every_action_is_stored(code: str) -> None:
    admin, token = _admin()
    actions = [*EXPLICIT_CODES, "x.create", "x.update", "x.delete", "auth.login", "reminder.run"]
    rows = {action: str(make("AuditLogEntry", actor=admin, action=action).pk) for action in actions}

    found = _ids_found(f"/fhir/AuditEvent?action={code}", token)

    shown = {rows[action] for action in actions if audit_action_code(action) == code}
    assert found & set(rows.values()) == shown


def returns_the_comma_list_in_the_next_link_when_a_comma_search_has_more_pages() -> None:
    _, token = _admin()
    for _ in range(3):
        make("Appointment", status="BOOKED")

    response = get("/fhir/Appointment?status=booked,cancelled&_count=1", token)

    next_link = next(item["url"] for item in response.json()["link"] if item["relation"] == "next")
    assert "status=booked%2Ccancelled" in next_link or "status=booked,cancelled" in next_link


@pytest.mark.parametrize(
    "query", ["name=a%00b", "name=a&name=b%00", "name%00=a", "name=a,b%00", "_id=a%00b"]
)
def returns_400_when_a_nul_byte_sits_in_any_repeat_or_name(query: str) -> None:
    response = get(f"/fhir/Organization?{query}", token_of(role="ADMIN"))

    assert response.status_code == 400
