"""Task 23a, spec 15.2 to 15.4: read and search `Appointment`. Visible rows are built from the
caller first (patient: own, clinician: own calendar and holds, admin: all); a search only narrows
them, so no count or link reveals what else exists."""

from uuid import UUID

from django.db.models import Model, Q, QuerySet
from django.db.models.functions import Coalesce

from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.fhir_appointment import FHIR_STATUS_OF_APPOINTMENT, PENDING
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_dates import day_bounds
from scheduling.domain.fhir_search import SearchQuery, parse_id
from scheduling.domain.vocabulary import Role, WaitlistStatus
from scheduling.models import Appointment, BookingHold, User, WaitlistEntry
from scheduling.use_cases import fhir_appointment_loading as loading
from scheduling.use_cases import fhir_loading as patient_loading
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_patient_reads import readable_patients
from scheduling.use_cases.fhir_reads import Filter, Part, SearchPage, Viewer, search_parts
from scheduling.use_cases.request_context import current_request_context

WAITLIST_STATUS_OF_FHIR = {
    "waitlist": WaitlistStatus.WAITING,
    "proposed": WaitlistStatus.OFFERED,
    "cancelled": WaitlistStatus.EXPIRED,
}
INCLUDE_TYPES = {
    "Appointment:patient": "Patient",
    "Appointment:practitioner": "Practitioner",
    "Appointment:location": "Location",
}


def read_appointment(identifier: str, caller: Caller) -> Result[Resource]:
    if caller.user is None:
        return Failure.unauthenticated()
    for part in _parts(caller.user, caller.role):
        if part.visible().filter(**{part.id_column: identifier}).exists():
            return Success(part.build([UUID(identifier)])[0])
    return Failure.not_found() if caller.role is Role.ADMIN else Failure.forbidden()


def search_appointments(query: SearchQuery, caller: Caller) -> Result[SearchPage]:
    if caller.user is None:
        return Failure.unauthenticated()
    parts = _parts(caller.user, caller.role)
    return Success(search_parts(parts, query, lambda found: _included(found, query, caller)))


def _parts(user: User, role: Role | None) -> tuple[Part, ...]:
    return (_booked_part(user, role), _waitlist_part(user, role), _hold_part(user, role))


def _booked_part(user: User, role: Role | None) -> Part:
    def rows() -> QuerySet[Model]:
        own = Appointment.objects.annotate(logical_id=Coalesce("waitlist_entry_id", "pk"))
        if role is Role.ADMIN:
            return own
        if role is Role.CLINICIAN:
            return own.filter(clinician__user=user)
        return own.filter(patient=user)

    return Part(
        visible=rows,
        everything=rows,
        id_column="logical_id",
        sort_columns={},
        filters={
            "patient": _equals("patient_id"),
            "practitioner": _equals("clinician__user_id"),
            "location": _location,
            "status": _booked_status,
            "date": starts_within("starts_at"),
            "service-type": _service_type,
        },
        build=lambda ids: loading.booked(ids, user.pk),
    )


def _waitlist_part(user: User, role: Role | None) -> Part:
    def rows() -> QuerySet[Model]:
        pending = WaitlistEntry.objects.exclude(status=WaitlistStatus.BOOKED)
        if role is Role.ADMIN:
            return pending
        return pending.filter(patient=user) if role is Role.PATIENT else pending.none()

    return Part(
        visible=rows,
        everything=rows,
        id_column="pk",
        sort_columns={},
        filters={
            "patient": _equals("patient_id"),
            "practitioner": _preferred_or_offered,
            "location": _equals("offered_appointment__room_id"),
            "status": _waitlist_status,
            "date": starts_within("offered_appointment__starts_at"),
            "service-type": _service_type,
        },
        build=loading.waiting,
    )


def _hold_part(user: User, role: Role | None) -> Part:
    def rows() -> QuerySet[Model]:
        live = BookingHold.objects.filter(expires_at__gt=current_request_context().now)
        if role is Role.ADMIN:
            return live
        return live.filter(clinician__user=user) if role is Role.CLINICIAN else live.none()

    return Part(
        visible=rows,
        everything=rows,
        id_column="pk",
        sort_columns={},
        filters={
            "patient": _nothing,
            "practitioner": _equals("clinician__user_id"),
            "location": _nothing,
            "status": lambda found, value: found if value == PENDING else found.none(),
            "date": starts_within("starts_at"),
            "service-type": _service_type,
        },
        build=loading.holds,
    )


def _equals(column: str) -> Filter:
    return lambda rows, value: rows.filter(**{column: value})


def _nothing(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    return rows.none()


def _location(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    return rows.filter(Q(room_id=value) | Q(room__department__hospital_id=value))


def _preferred_or_offered(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    return rows.filter(
        Q(preferred_clinician__user_id=value) | Q(offered_appointment__clinician__user_id=value)
    )


def _service_type(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    identifier = parse_id(value)
    return rows.filter(appointment_type_id=identifier) if identifier else rows.none()


def _booked_status(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    wanted = [internal for internal, fhir in FHIR_STATUS_OF_APPOINTMENT.items() if fhir == value]
    return rows.filter(status__in=wanted)


def _waitlist_status(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    wanted = WAITLIST_STATUS_OF_FHIR.get(value)
    return rows.filter(status=wanted) if wanted else rows.none()


def starts_within(column: str) -> Filter:
    def narrow(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
        first, last = day_bounds([value])
        if first is not None:
            rows = rows.filter(**{f"{column}__gte": first})
        return rows if last is None else rows.filter(**{f"{column}__lt": last})

    return narrow


def _included(found: list[Resource], query: SearchQuery, caller: Caller) -> list[Resource]:
    wanted = {INCLUDE_TYPES[name] for name in query.include if name in INCLUDE_TYPES}
    references = _references(found)
    built: list[Resource] = []
    if "Patient" in wanted and caller.user is not None:
        readable = readable_patients(caller)
        allowed = [] if readable is None else list(readable.filter(pk__in=references["Patient"]))
        built += patient_loading.patients([item.pk for item in allowed])
    if "Practitioner" in wanted:
        load = (
            patient_loading.practitioners_with_contact
            if caller.viewer is Viewer.STAFF
            else patient_loading.practitioners
        )
        built += load(sorted(references["Practitioner"]))
    if "Location" in wanted:
        built += patient_loading.room_locations(sorted(references["Location"]))
    return built


def _references(found: list[Resource]) -> dict[str, set[UUID]]:
    wanted: dict[str, set[UUID]] = {"Patient": set(), "Practitioner": set(), "Location": set()}
    for resource in found:
        participants = resource.get("participant")
        for item in participants if isinstance(participants, list) else []:
            kind, _, identifier = str(item["actor"]["reference"]).partition("/")
            wanted[kind].add(UUID(identifier))
    return wanted
