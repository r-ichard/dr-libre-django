"""Records for the record-page walk: an own and an other record for each family, a hold per caller,
the id each placeholder takes on each leg, and the answers each leg accepts. Used by
test_page_access_records.py; holds no test."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from django.db.models import Model
from django.test import Client

from scheduling.models import AvailabilityRule, ClinicianProfile, User
from scheduling.models.builders import add_clinician, make, make_clinic, make_user
from scheduling.views.hold_cookie import HOLD_COOKIE
from scheduling.views.pages.booking_pages_support import FORM, details_path
from scheduling.views.pages.browser_support import browser_client, browser_post
from scheduling.views.pages.page_walk_support import World, fill_route
from scheduling.views.pages.test_page_access_rows import Answer, Row
from scheduling.views.pages.test_page_access_walk import Caller, _wanted

Leg = Literal["own", "other", "missing"]
UUID_PLACEHOLDER = re.compile(r"<uuid:(\w+)>")
# Placeholders whose record has an owner, so another user's record can stand in for it.
OWNED_PLACEHOLDERS = frozenset({"appointment_id", "rule_id", "time_off_id", "hold_id"})
OWNED_ROUTE_PREFIXES = ("admin-console/users/", "admin-console/clinicians/")
# Booking details and reschedule reviews answer 404 without a slot; this one is free on a Monday.
FREE_SLOT = "2030-01-14T10:00:00Z"
SLOT_ROUTE_SUFFIXES = ("/details", "/reschedule/review")


@dataclass(frozen=True)
class Records:
    world: World
    rule: AvailabilityRule
    other_rule: AvailabilityRule
    time_off: Model
    other_time_off: Model
    other_appointment: Model
    other_clinician: ClinicianProfile
    other_patient: User
    other_hold: UUID
    holds: dict[Caller, UUID]


def records_of(world: World, clients: Mapping[Caller, Client]) -> Records:
    clinic = world.clinic
    other_clinician = add_clinician(clinic.department)
    other_patient = make_user()
    return Records(
        world=world,
        rule=_rule_of(clinic.clinician),
        other_rule=_rule_of(other_clinician),
        time_off=make("TimeOff", clinician=clinic.clinician),
        other_time_off=make("TimeOff", clinician=other_clinician),
        other_appointment=make(
            "Appointment",
            patient=other_patient,
            clinician=other_clinician,
            appointment_type=clinic.appointment_type,
        ),
        other_clinician=other_clinician,
        other_patient=other_patient,
        other_hold=_hold_made_by(browser_client(), "other.hold@example.test"),
        holds={
            caller: _hold_carried_to(client, f"{caller}.hold@example.test")
            for caller, client in clients.items()
        },
    )


def _hold_carried_to(client: Client, email: str) -> UUID:
    """Only a visitor's browser makes a hold (section 7.2: staff are refused, a signed-in patient
    books). The caller's browser then carries the hold cookie, as one does after signing in."""
    visitor = browser_client()
    hold_id = _hold_made_by(visitor, email)
    client.cookies[HOLD_COOKIE] = visitor.cookies[HOLD_COOKIE].value
    return hold_id


def _hold_made_by(client: Client, email: str) -> UUID:
    """A hold needs a slot nobody holds, so each hold books a clinic of its own."""
    response = browser_post(client, details_path(make_clinic()), {**FORM, "email": email})
    assert response.status_code == 303  # noqa: S101 - a refused hold is a broken test setup
    return UUID(response["Location"].split("/")[3])


def _rule_of(clinician: ClinicianProfile) -> AvailabilityRule:
    rule = AvailabilityRule.objects.filter(clinician=clinician).first()
    assert rule is not None  # noqa: S101 - add_clinician makes one rule
    return rule


def has_other_record(route: str, caller: Caller) -> bool:
    """Whether another user's record can answer for this caller on this route. An admin manages
    every hospital, so no admin-console page hides another user's record from it."""
    if route.startswith("admin-console/") and caller == "admin":
        return False
    names = set(UUID_PLACEHOLDER.findall(route))
    return bool(names & OWNED_PLACEHOLDERS) or route.startswith(OWNED_ROUTE_PREFIXES)


def ids_for(route: str, leg: Leg, caller: Caller, records: Records) -> dict[str, UUID]:
    """The id of each `<uuid:name>` of `route` on this leg. An owner-less record is the same on
    every leg; only has_other_record decides whether the other leg is walked."""
    return {
        name: _id_of(name, route, leg, caller, records) for name in UUID_PLACEHOLDER.findall(route)
    }


def path_for(route: str, leg: Leg, caller: Caller, records: Records) -> str:
    """The address the walk requests. A booking or reschedule page also needs a provider and a
    slot; without them it answers 404 to every caller, which would hide the ownership answer."""
    address = fill_route(route, ids_for(route, leg, caller, records))
    if not route.endswith(SLOT_ROUTE_SUFFIXES):
        return address
    provider = records.world.clinic.clinician.pk
    return f"{address}?provider={provider}&starts_at={FREE_SLOT}"


def _id_of(name: str, route: str, leg: Leg, caller: Caller, records: Records) -> UUID:
    if leg == "missing":
        return uuid4()
    other = leg == "other"
    clinic = records.world.clinic
    match name:
        case "appointment_id":
            return _pk(records.other_appointment if other else records.world.appointment)
        case "rule_id":
            return _pk(records.other_rule if other else records.rule)
        case "time_off_id":
            return _pk(records.other_time_off if other else records.time_off)
        case "hold_id":
            return records.other_hold if other else records.holds[caller]
        case "provider_id":
            return _pk(records.other_clinician if other else clinic.clinician)
        case "appointment_type_id":
            return _pk(clinic.appointment_type)
        case "hospital_id":
            return clinic.department.hospital_id
        case "specialty_id":
            return clinic.clinician.specialty_id
        case "record_id":
            return _admin_record_id(route, records, other)
    raise ValueError(f"no record fills <uuid:{name}> of {route}")


def _admin_record_id(route: str, records: Records, other: bool) -> UUID:
    clinic = records.world.clinic
    kind = route.split("/")[1]
    match kind:
        case "users":
            return _pk(records.other_patient if other else clinic.patient)
        case "clinicians":
            return _pk(records.other_clinician if other else clinic.clinician)
        case "hospitals":
            return clinic.department.hospital_id
        case "specialties":
            return clinic.clinician.specialty_id
        case "departments":
            return _pk(clinic.department)
        case "rooms":
            room_id = records.world.room_id
            assert room_id is not None  # noqa: S101 - make_world makes a room
            return room_id
        case "appointment-types":
            return _pk(clinic.appointment_type)
    raise ValueError(f"no record kind {kind} for {route}")


def accepted_answers(leg: Leg, row: Row, caller: Caller) -> frozenset[str]:
    """The own record gets the row's answer. Another user's record gets the row's answer, or 403
    or 404 where the row admits the caller. A missing record gets 404 where the row admits the
    caller, else the row's answer."""
    wanted = _wanted(row, caller)
    if leg == "own" or wanted != Answer.OK:
        return frozenset({wanted})
    if leg == "other":
        return frozenset({Answer.FORBIDDEN, Answer.NOT_FOUND})
    return frozenset({Answer.NOT_FOUND})


def other_marks(records: Records) -> tuple[str, ...]:
    """Text that would show another user's record on a page: its ids and its owners' emails."""
    return (
        str(records.other_appointment.pk),
        str(records.other_rule.pk),
        str(records.other_time_off.pk),
        str(records.other_hold),
        str(records.other_clinician.pk),
        str(records.other_patient.pk),
        records.other_patient.email,
        _email_of(records.other_clinician),
    )


def _email_of(clinician: ClinicianProfile) -> str:
    user = clinician.user
    assert isinstance(user, User)  # noqa: S101 - a clinician is always a user
    return user.email


def leaks(body: str, marks: Iterable[str]) -> bool:
    return any(mark in body for mark in marks)


def _pk(record: Model) -> UUID:
    found = record.pk
    assert isinstance(found, UUID)  # noqa: S101 - every record here has a UUID key
    return found
