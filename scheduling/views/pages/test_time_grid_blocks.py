"""Task 17f: what a block of the clinician calendar shows and says, read from the rendered page."""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from django.test import Client

from scheduling.models import Room, TimeOff, User
from scheduling.models.builders import Clinic, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, signed_in_patient

pytestmark = pytest.mark.django_db
BERLIN = ZoneInfo("Europe/Berlin")
BLOCK = re.compile(r'<li class="time-grid-item [^"]*">.*?</li>', re.S)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _local(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 23, hour, minute, tzinfo=BERLIN).astimezone(UTC)


def _blocks(clinic: Clinic) -> list[str]:
    user = clinic.clinician.user
    assert isinstance(user, User)
    client: Client = signed_in_patient(user)
    html = client.get("/clinician/calendar?week=2026-11-23").content.decode()
    return BLOCK.findall(html)


def _room(clinic: Clinic) -> Room:
    room = make("Room", department=clinic.department, name="Room Quartz")
    assert isinstance(room, Room)
    return room


def _book(clinic: Clinic, minutes: int, room: Room | None = None) -> None:
    make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        room=room,
        starts_at=_local(12),
        ends_at=_local(12, minutes),
    )


def returns_room_and_status_after_type_and_patient_when_appointment_has_a_room() -> None:
    clinic = make_clinic()
    _book(clinic, 30, _room(clinic))

    (block,) = _blocks(clinic)

    drawn = re.findall(r'<span class="time-grid-item__line[^"]*">(.*?)</span>', block, re.S)
    texts = [re.sub(r"<[^>]+>", "", each).strip() for each in drawn]
    assert texts[1:3] == [clinic.appointment_type.name, clinic.patient.full_name]
    assert texts[3] == "Room Quartz"
    assert len(texts) == 5 and texts[4]


def returns_lines_past_the_third_cut_and_status_icon_first_when_block_is_one_row() -> None:
    clinic = make_clinic()
    _book(clinic, 30, _room(clinic))

    (block,) = _blocks(clinic)

    lines = re.findall(r'<span class="(time-grid-item__line[^"]*)">', block)
    assert [("--cut" in each) for each in lines] == [False, False, False, True, True]
    assert '<svg class="icon"' in block.split('time-grid-item__line time-grid-item__time">')[1]
    assert block.count("<svg") == 1


def returns_every_line_drawn_hidden_and_spoken_once_when_block_is_a_link() -> None:
    clinic = make_clinic()
    _book(clinic, 30)

    (block,) = _blocks(clinic)

    assert '<span class="time-grid-item__lines" aria-hidden="true">' in block
    spoken = re.search(r'<span class="visually-hidden">(.*?)</span>', block, re.S)
    assert spoken is not None and clinic.patient.full_name in spoken.group(1)


def returns_link_to_the_time_off_row_when_a_time_off_is_drawn() -> None:
    clinic = make_clinic()
    row = make(
        "TimeOff", clinician=clinic.clinician, starts_at=_local(12), ends_at=_local(14), reason="x"
    )
    assert isinstance(row, TimeOff)

    (block,) = _blocks(clinic)

    assert f'href="/clinician/time-off#time-off-{row.pk}"' in block
    assert "time-grid-behind" in block and "time-grid-front" not in block
