"""Sections 6 and 14 GET /search/*: public search. Reads no session, nothing about a patient.
Cost: two catalogue queries and one schedule load for all candidates, however many match."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, overload
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.free_slots import SlotType, TimeRange
from scheduling.domain.search_availability import BookableType, next_starts, shortest_type
from scheduling.domain.search_matching import (
    HORIZON,
    ProviderRecord,
    matches_text,
    search_range,
    time_of_day_of,
)
from scheduling.domain.search_ordering import Sortable, haversine_kilometres, paginate, sort_results
from scheduling.domain.search_query import Location, SearchQuery
from scheduling.domain.search_results import summarise
from scheduling.domain.slot_search import ClinicianSchedule
from scheduling.use_cases.schedule_loading import load_schedules
from scheduling.use_cases.search_catalog import CatalogProvider, load_catalog
from scheduling.use_cases.search_types import (
    AnyResult,
    HospitalResult,
    Opening,
    ProviderResult,
    SearchPage,
    SpecialtyResult,
)

PROVIDER_STARTS = 3
AGGREGATE_STARTS = 1


@dataclass(frozen=True)
class Candidate:
    provider: CatalogProvider
    appointment_type: BookableType
    starts: list[datetime]


@overload
def search_public(
    kind: Literal["providers"], query: SearchQuery, now: datetime
) -> SearchPage[ProviderResult]: ...
@overload
def search_public(
    kind: Literal["hospitals"], query: SearchQuery, now: datetime
) -> SearchPage[HospitalResult]: ...
@overload
def search_public(
    kind: Literal["specialties"], query: SearchQuery, now: datetime
) -> SearchPage[SpecialtyResult]: ...
@overload
def search_public(kind: str, query: SearchQuery, now: datetime) -> SearchPage[AnyResult]: ...
def search_public(kind: str, query: SearchQuery, now: datetime) -> SearchPage[AnyResult]:
    candidates = _candidates(
        query, now, PROVIDER_STARTS if kind == "providers" else AGGREGATE_STARTS
    )
    if kind == "providers":
        entries = [(_sortable(item, query), _provider_result(item)) for item in candidates]
        return _page(query, entries)
    if kind == "hospitals":
        return _page(query, _hospital_entries(candidates, query))
    return _page(query, _specialty_entries(candidates, query))


def _candidates(query: SearchQuery, now: datetime, wanted: int) -> list[Candidate]:
    matching = [
        (provider, chosen)
        for provider in load_catalog()
        if _matches(provider, query) and (chosen := _chosen_type(provider, query)) is not None
    ]
    schedules = _schedules(matching, now)
    candidates = [
        Candidate(
            provider,
            chosen,
            _starts(chosen, provider.time_zone, schedules[provider.id], query, now, wanted),
        )
        for provider, chosen in matching
    ]
    narrowed = query.window != "any" or query.earliest_date or query.time_of_day
    return [candidate for candidate in candidates if candidate.starts or not narrowed]


def _chosen_type(provider: CatalogProvider, query: SearchQuery) -> BookableType | None:
    if query.appointment_type_id is None:
        return shortest_type(provider.types)
    named = [item for item in provider.types if item.id == query.appointment_type_id]
    return named[0] if named else None


def _matches(provider: CatalogProvider, query: SearchQuery) -> bool:
    record = ProviderRecord(
        provider.id,
        provider.full_name,
        provider.title,
        provider.hospital_name,
        provider.city,
        provider.time_zone,
        provider.specialty_name,
        provider.department_name,
        tuple(item.name for item in provider.types),
    )
    return (
        matches_text(query.text, record)
        and query.specialty_id in (None, provider.specialty_id)
        and query.hospital_id in (None, provider.hospital_id)
        and (query.city is None or query.city.casefold() == provider.city.casefold())
    )


def _schedules(
    matching: list[tuple[CatalogProvider, BookableType]], now: datetime
) -> dict[UUID, ClinicianSchedule]:
    # The largest buffer loads a superset; free_slots applies each type's own buffer.
    buffer = max((chosen.buffer_minutes for _, chosen in matching), default=0)
    slot_type = SlotType(timedelta(0), timedelta(minutes=buffer))
    ids = [provider.id for provider, _ in matching]
    return load_schedules(ids, slot_type, TimeRange(now, now + HORIZON), now)


def _starts(
    chosen: BookableType,
    time_zone: str,
    schedule: ClinicianSchedule,
    query: SearchQuery,
    now: datetime,
    wanted: int,
) -> list[datetime]:
    zone = ZoneInfo(time_zone)
    window = search_range(now, zone, query.window, query.earliest_date)
    if window is None:
        return []
    slot_type = SlotType(
        timedelta(minutes=chosen.duration_minutes), timedelta(minutes=chosen.buffer_minutes)
    )
    period = query.time_of_day

    def in_period(start: datetime) -> bool:
        return period is None or time_of_day_of(start, zone) == period

    return next_starts(schedule, slot_type, window, now, zone, wanted, in_period)


def _first_start(candidate: Candidate) -> datetime | None:
    return candidate.starts[0] if candidate.starts else None


def _earliest_opening(members: list[Candidate]) -> Opening | None:
    open_members = [member for member in members if member.starts]
    if not open_members:
        return None
    best = min(open_members, key=lambda member: member.starts[0])
    return Opening(
        best.starts[0], best.provider.id, best.appointment_type.id, best.provider.time_zone
    )


def _distance(candidate: Candidate, location: Location | None) -> float | None:
    provider = candidate.provider
    if location is None or provider.latitude is None or provider.longitude is None:
        return None
    return haversine_kilometres(
        location.latitude, location.longitude, provider.latitude, provider.longitude
    )


def _sortable(candidate: Candidate, query: SearchQuery) -> Sortable:
    provider = candidate.provider
    return Sortable(
        provider.id,
        provider.full_name,
        _first_start(candidate),
        _distance(candidate, query.location),
    )


def _provider_result(candidate: Candidate) -> ProviderResult:
    provider, chosen = candidate.provider, candidate.appointment_type
    return ProviderResult(
        id=provider.id,
        full_name=provider.full_name,
        title=provider.title,
        specialty_id=provider.specialty_id,
        specialty_name=provider.specialty_name,
        hospital_id=provider.hospital_id,
        hospital_name=provider.hospital_name,
        city=provider.city,
        time_zone=provider.time_zone,
        department_id=provider.department_id,
        department_name=provider.department_name,
        appointment_type_id=chosen.id,
        appointment_type_name=chosen.name,
        appointment_type_minutes=chosen.duration_minutes,
        next_starts=candidate.starts,
        has_availability=bool(candidate.starts),
    )


def _group[Key](
    candidates: list[Candidate], key_of: Callable[[CatalogProvider], Key]
) -> dict[Key, list[Candidate]]:
    groups: dict[Key, list[Candidate]] = {}
    for candidate in candidates:
        groups.setdefault(key_of(candidate.provider), []).append(candidate)
    return groups


def _nearest(members: list[Candidate], query: SearchQuery) -> float | None:
    distances = [d for member in members if (d := _distance(member, query.location)) is not None]
    return min(distances, default=None)


def _hospital_entries(
    candidates: list[Candidate], query: SearchQuery
) -> list[tuple[Sortable, HospitalResult]]:
    entries: list[tuple[Sortable, HospitalResult]] = []
    for hospital_id, members in _group(candidates, lambda provider: provider.hospital_id).items():
        first = members[0].provider
        summary = summarise([_first_start(member) for member in members])
        opening = _earliest_opening(members)
        result = HospitalResult(
            id=hospital_id,
            name=first.hospital_name,
            street_address=first.street_address,
            postal_code=first.postal_code,
            city=first.city,
            country=first.country,
            time_zone=first.time_zone,
            specialty_names=sorted({member.provider.specialty_name for member in members}),
            bookable_provider_count=summary.provider_count,
            providers_with_availability_count=summary.with_availability_count,
            earliest=opening,
            has_availability=opening is not None,
        )
        sortable = Sortable(
            hospital_id, result.name, summary.earliest_start, _nearest(members, query)
        )
        entries.append((sortable, result))
    return entries


def _specialty_entries(
    candidates: list[Candidate], query: SearchQuery
) -> list[tuple[Sortable, SpecialtyResult]]:
    entries: list[tuple[Sortable, SpecialtyResult]] = []
    for specialty_id, members in _group(candidates, lambda provider: provider.specialty_id).items():
        summary = summarise([_first_start(member) for member in members])
        opening = _earliest_opening(members)
        result = SpecialtyResult(
            id=specialty_id,
            name=members[0].provider.specialty_name,
            provider_count=summary.provider_count,
            hospital_count=len({member.provider.hospital_id for member in members}),
            earliest=opening,
            has_availability=opening is not None,
        )
        sortable = Sortable(
            specialty_id, result.name, summary.earliest_start, _nearest(members, query)
        )
        entries.append((sortable, result))
    return entries


def _page[Result: ProviderResult | HospitalResult | SpecialtyResult](
    query: SearchQuery, entries: list[tuple[Sortable, Result]]
) -> SearchPage[Result]:
    by_id = {sortable.id: result for sortable, result in entries}
    ordered = [by_id[item.id] for item in sort_results([s for s, _ in entries], query.sort)]
    page = paginate(ordered, query.page, query.page_size)
    return SearchPage(page.items, page.total, page.page, page.page_count, query.page_size)
