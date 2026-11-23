"""The request each route that names a record receives from each caller, sent as the route's real
client sends it: a browser's Origin and cookie, the record's id in the path, and a body of the
fields the route accepts."""

from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

from django.http import HttpResponseBase

from scheduling.models import Appointment
from scheduling.views.test_api_access_requests import JSON, _client
from scheduling.views.test_api_access_rows import Caller
from scheduling.views.test_api_access_world import World

RecordSender = Callable[[World, Caller, UUID], HttpResponseBase]
RESCHEDULE_SHIFT = timedelta(hours=4)
CANCEL_REASON = "Plans changed"


def _with_body(path_template: str, body: Callable[[UUID], dict[str, object]]) -> RecordSender:
    def send(world: World, caller: Caller, record_id: UUID) -> HttpResponseBase:
        path = path_template.format(record_id)
        return _client(world.clients, caller).post(path, body(record_id), content_type=JSON)

    return send


def _get_record(path_template: str) -> RecordSender:
    def send(world: World, caller: Caller, record_id: UUID) -> HttpResponseBase:
        return _client(world.clients, caller).get(path_template.format(record_id))

    return send


def _no_fields(record_id: UUID) -> dict[str, object]:
    return {}


def _cancel_reason(record_id: UUID) -> dict[str, object]:
    return {"reason": CANCEL_REASON}


def _four_hours_later(record_id: UUID) -> dict[str, object]:
    starts_at = Appointment.objects.get(pk=record_id).starts_at + RESCHEDULE_SHIFT
    return {"starts_at": starts_at.isoformat()}


APPOINTMENT_ACTION = "/api/v1/appointments/{}/"
WAITLIST_ACTION = "/api/v1/waitlist/{}/"

RECORD_SENDERS: dict[tuple[str, str], RecordSender] = {
    ("POST", "api/v1/appointments/<uuid:appointment_id>/cancel"): _with_body(
        APPOINTMENT_ACTION + "cancel", _cancel_reason
    ),
    ("POST", "api/v1/appointments/<uuid:appointment_id>/reschedule"): _with_body(
        APPOINTMENT_ACTION + "reschedule", _four_hours_later
    ),
    ("POST", "api/v1/appointments/<uuid:appointment_id>/check-in"): _with_body(
        APPOINTMENT_ACTION + "check-in", _no_fields
    ),
    ("POST", "api/v1/appointments/<uuid:appointment_id>/complete"): _with_body(
        APPOINTMENT_ACTION + "complete", _no_fields
    ),
    ("POST", "api/v1/appointments/<uuid:appointment_id>/no-show"): _with_body(
        APPOINTMENT_ACTION + "no-show", _no_fields
    ),
    ("POST", "api/v1/waitlist/<uuid:entry_id>/accept"): _with_body(
        WAITLIST_ACTION + "accept", _no_fields
    ),
    ("POST", "api/v1/waitlist/<uuid:entry_id>/offer"): _with_body(
        WAITLIST_ACTION + "offer", _no_fields
    ),
    ("GET", "api/v1/hospitals/<uuid:hospital_id>"): _get_record("/api/v1/hospitals/{}"),
    ("GET", "api/v1/providers/<uuid:provider_id>"): _get_record("/api/v1/providers/{}"),
    ("GET", "api/v1/specialties/<uuid:specialty_id>"): _get_record("/api/v1/specialties/{}"),
}
