"""Task 23, spec 15.5, 15.6: `Slot` is never stored. Free slots come from `find_free_slots`, the
use case `GET /api/v1/slots` runs. A clinician sees busy slots of their own schedules, an admin
of all; nobody else sees one or learns that one exists."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.failure import Failure, FailureCode, FieldMessage, Result, Success
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_dates import bounded_window
from scheduling.domain.fhir_search import SearchQuery
from scheduling.domain.fhir_slot import (
    ACTOR_PARAMETER,
    SEARCH_NAMES,
    RuleCover,
    SlotSource,
    schedule_of,
    slot_resource,
)
from scheduling.domain.fhir_slot_id import parse_slot_id
from scheduling.domain.free_slots import AvailabilityWindow, TimeRange, free_slots
from scheduling.domain.slot_search import MAXIMUM_QUERY_DAYS
from scheduling.domain.slot_status import BUSY_STATUSES, FREE, busy_status
from scheduling.domain.vocabulary import Role
from scheduling.models import (
    AppointmentType,
    AvailabilityRule,
    ClinicianProfile,
)
from scheduling.use_cases import fhir_loading as loading
from scheduling.use_cases.fhir_busy_slots import busy_intervals
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_reads import SearchPage
from scheduling.use_cases.free_slots_query import FoundSlots, find_free_slots
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.schedule_loading import (
    active_appointment_type,
    department_clinicians,
    online_only_for,
    slot_type_of,
)

START_PROBLEM = FieldMessage("start", "Give a start range of at most 31 days: ge and lt.")
TYPE_PROBLEM = FieldMessage("service-type", "Give the id of an appointment type.")
EMPTY_PAGE = SearchPage(0, [], [])


@dataclass(frozen=True)
class Placed:
    start: datetime
    rule_id: UUID
    status: str


@dataclass(frozen=True)
class RuleRow:
    id: UUID
    clinician_id: UUID
    practitioner_id: UUID
    room_id: UUID | None
    cover: RuleCover


@dataclass(frozen=True)
class SlotFilters:
    schedules: frozenset[str]
    actors: frozenset[str]
    statuses: frozenset[str]

    def accepts(self, rule: RuleRow) -> bool:
        actors = {str(rule.practitioner_id), str(rule.room_id)}
        return (not self.schedules or str(rule.id) in self.schedules) and (
            not self.actors or bool(self.actors & actors)
        )


@dataclass(frozen=True)
class Grid:
    """What one search lays slots over: the type, the range and the rules of the clinicians."""

    appointment_type: AppointmentType
    found: FoundSlots
    window: TimeRange
    rows: dict[UUID, RuleRow]
    filters: SlotFilters

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.found.time_zone)

    def rule_of(self, clinician_id: UUID, start: datetime) -> UUID | None:
        covers = [row.cover for row in self.rows.values() if row.clinician_id == clinician_id]
        rule_id = schedule_of(covers, start, self.zone)
        return rule_id if rule_id is not None and self.filters.accepts(self.rows[rule_id]) else None


def _parse_type_id(given: list[str]) -> UUID | Failure:
    try:
        return UUID(given[0])
    except (ValueError, IndexError):
        return Failure.invalid_input([TYPE_PROBLEM])


def search_slots(query: SearchQuery, caller: Caller) -> Result[SearchPage]:
    values = {name: [value for key, value in query.filters if key == name] for name in SEARCH_NAMES}
    window = bounded_window(values["start"], timedelta(days=MAXIMUM_QUERY_DAYS))
    if window is None:
        return Failure.invalid_input([START_PROBLEM])
    online_only = online_only_for(caller.user)
    type_id = _parse_type_id(values["service-type"])
    if isinstance(type_id, Failure):
        return type_id
    appointment_type = active_appointment_type(type_id, online_only)
    if appointment_type is None:
        return Success(EMPTY_PAGE)
    found = find_free_slots(appointment_type.pk, None, TimeRange(*window), online_only)
    if isinstance(found, Failure):
        return Success(EMPTY_PAGE) if found.code is FailureCode.NOT_FOUND else found
    filters = SlotFilters(
        frozenset(values["schedule"]),
        frozenset(values[ACTOR_PARAMETER]),
        frozenset(values["status"] or [FREE]),
    )
    free_by_clinician = _free_by_clinician(found.value)
    busy_ids = _busy_clinicians(appointment_type, caller, filters)
    rows = _rule_rows(set(free_by_clinician) | busy_ids)
    grid = Grid(appointment_type, found.value, TimeRange(*window), rows, filters)
    placed = _free_placed(grid, free_by_clinician) + _busy_placed(grid, busy_ids, free_by_clinician)
    placed.sort(key=lambda item: (item.start, str(item.rule_id)))
    page = placed[query.offset : query.offset + query.count]
    resources = [_resource(item, appointment_type, found.value) for item in page]
    return Success(SearchPage(len(placed), resources, _included(query, page)))


def read_slot(identifier: str, caller: Caller) -> Result[Resource]:
    """A free slot the same caller would find by search; anything else is not found."""
    parsed = parse_slot_id(identifier)
    rule = AvailabilityRule.objects.filter(pk=parsed[0]).first() if parsed else None
    if parsed is None or rule is None:
        return Failure.not_found()
    _, type_id, start = parsed
    online_only = online_only_for(caller.user)
    appointment_type = active_appointment_type(type_id, online_only)
    if appointment_type is None:
        return Failure.not_found()
    window = TimeRange(start, start + slot_type_of(appointment_type).duration)
    found = find_free_slots(type_id, rule.clinician_id, window, online_only)
    if isinstance(found, Failure):
        return found
    rows = _rule_rows({rule.clinician_id})
    grid = Grid(
        appointment_type,
        found.value,
        window,
        rows,
        SlotFilters(frozenset(), frozenset(), frozenset()),
    )
    offered = any(offer.start == start for offer in found.value.offers)
    if not offered or grid.rule_of(rule.clinician_id, start) != rule.pk:
        return Failure.not_found()
    return Success(_resource(Placed(start, rule.pk, FREE), appointment_type, found.value))


def _free_by_clinician(found: FoundSlots) -> dict[UUID, set[datetime]]:
    starts: dict[UUID, set[datetime]] = {}
    for offer in found.offers:
        for clinician_id in offer.clinician_ids:
            starts.setdefault(clinician_id, set()).add(offer.start)
    return starts


def _free_placed(grid: Grid, free_by_clinician: dict[UUID, set[datetime]]) -> list[Placed]:
    if FREE not in grid.filters.statuses:
        return []
    placed = []
    for clinician_id, starts in free_by_clinician.items():
        for start in starts:
            rule_id = grid.rule_of(clinician_id, start)
            if rule_id is not None:
                placed.append(Placed(start, rule_id, FREE))
    return placed


def _busy_clinicians(
    appointment_type: AppointmentType, caller: Caller, filters: SlotFilters
) -> set[UUID]:
    """Who may be asked about busy slots: an admin all, a clinician only themselves."""
    if not filters.statuses & set(BUSY_STATUSES) or caller.user is None:
        return set()
    candidates = set(
        department_clinicians(appointment_type, None, online_only=False).values_list(
            "pk", flat=True
        )
    )
    if caller.role is Role.ADMIN:
        return candidates
    if caller.role is Role.CLINICIAN:
        own = ClinicianProfile.objects.filter(user=caller.user).values_list("pk", flat=True)
        return candidates & set(own)
    return set()


def _busy_placed(
    grid: Grid, clinician_ids: Collection[UUID], free_by_clinician: dict[UUID, set[datetime]]
) -> list[Placed]:
    if not clinician_ids:
        return []
    slot_type = slot_type_of(grid.appointment_type)
    now = current_request_context().now
    busy = busy_intervals(clinician_ids, grid.window, slot_type.buffer, now)
    placed = []
    for clinician_id in clinician_ids:
        windows = [
            row.cover.window for row in grid.rows.values() if row.clinician_id == clinician_id
        ]
        every_start = free_slots(windows, slot_type, [], [], grid.window, now, grid.zone)
        for start in set(every_start) - free_by_clinician.get(clinician_id, set()):
            status = busy_status(start, slot_type.duration, slot_type.buffer, *busy[clinician_id])
            rule_id = grid.rule_of(clinician_id, start)
            if status in grid.filters.statuses and rule_id is not None:
                placed.append(Placed(start, rule_id, status))
    return placed


def _rule_rows(clinician_ids: Collection[UUID]) -> dict[UUID, RuleRow]:
    rules = AvailabilityRule.objects.filter(clinician_id__in=clinician_ids)
    return {rule.pk: _row_of(rule) for rule in rules.select_related("clinician")}


def _row_of(rule: AvailabilityRule) -> RuleRow:
    window = AvailabilityWindow(
        rule.weekday,
        rule.start_time,
        rule.end_time,
        timedelta(minutes=rule.slot_step_minutes),
        rule.valid_from,
        rule.valid_to,
    )
    practitioner_id = rule.clinician.user_id
    return RuleRow(
        rule.pk, rule.clinician_id, practitioner_id, rule.room_id, RuleCover(rule.pk, window)
    )


def _resource(item: Placed, appointment_type: AppointmentType, found: FoundSlots) -> Resource:
    return slot_resource(
        SlotSource(
            item.rule_id,
            appointment_type.pk,
            appointment_type.name,
            item.start,
            found.duration,
            item.status,
        )
    )


def _included(query: SearchQuery, page: list[Placed]) -> list[Resource]:
    if "Slot:schedule" not in query.include or not page:
        return []
    return loading.schedules(sorted({item.rule_id for item in page}, key=str))
