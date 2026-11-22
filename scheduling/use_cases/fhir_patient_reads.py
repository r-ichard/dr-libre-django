"""Task 23, spec 12.3, 15.4, 15.5: who may read which `Patient`. The readable set is built from
the caller first (patient: self; clinician: own appointments; admin: all); a search only narrows
it, so no count, link or error says whether another one exists."""

from uuid import UUID

from django.db.models import Model, QuerySet

from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_dates import day_bounds
from scheduling.domain.fhir_search import SearchQuery
from scheduling.domain.vocabulary import Role
from scheduling.models import Appointment, User
from scheduling.use_cases import fhir_loading as loading
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_reads import Part, SearchPage, search_part


def readable_patients(caller: Caller) -> QuerySet[User] | None:
    """None when the caller has no token: nothing is readable and the answer is 401."""
    if caller.user is None:
        return None
    patients = User.objects.filter(role=Role.PATIENT)
    if caller.role is Role.ADMIN:
        return patients
    if caller.role is Role.CLINICIAN:
        seen = Appointment.objects.filter(clinician__user=caller.user).values("patient_id")
        return patients.filter(pk__in=seen)
    return patients.filter(pk=caller.user.pk)


def read_patient(identifier: str, caller: Caller) -> Result[Resource]:
    readable = readable_patients(caller)
    if readable is None:
        return Failure.unauthenticated()
    if readable.filter(pk=identifier).exists():
        return Success(loading.patients([UUID(identifier)])[0])
    return Failure.not_found() if caller.role is Role.ADMIN else Failure.forbidden()


def search_patients(query: SearchQuery, caller: Caller) -> Result[SearchPage]:
    readable = readable_patients(caller)
    if readable is None:
        return Failure.unauthenticated()
    part = Part(
        visible=lambda: readable,
        everything=lambda: readable,
        id_column="pk",
        sort_columns={"name": "full_name", "birthdate": "date_of_birth"},
        filters={
            "name": lambda rows, value: rows.filter(full_name__icontains=value),
            "email": lambda rows, value: rows.filter(email__iexact=value),
            "phone": lambda rows, value: rows.filter(phone=value),
            "birthdate": _born_within,
        },
        build=loading.patients,
    )
    return Success(search_part(part, query))


def _born_within(rows: QuerySet[Model], value: str) -> QuerySet[Model]:
    first, last = day_bounds([value])
    if first is not None:
        rows = rows.filter(date_of_birth__gte=first)
    return rows if last is None else rows.filter(date_of_birth__lte=last)
