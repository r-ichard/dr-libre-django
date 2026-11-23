"""Section 4: one submission reports every error, not one round per error."""

import re

import pytest

from scheduling.models import ClinicianProfile, Room
from scheduling.models.builders import make
from scheduling.views.pages.admin_support import admin_client, admin_post

pytestmark = pytest.mark.django_db

CONSOLE = "/admin-console"
WEIGHT_MESSAGE = "Use a whole number of 1 or more."
ROOM_MESSAGE = "Choose an active room of this department."


def returns_both_messages_and_both_summary_links_when_weight_and_room_are_wrong() -> None:
    clinician = make("User", role="CLINICIAN")
    department = make("Department")
    foreign_room = make("Room", department=make("Department"))
    assert isinstance(foreign_room, Room)
    values = {
        "user": str(clinician.pk), "department": str(department.pk),
        "specialty": str(make("Specialty").pk), "title": "Dr", "bio": "",
        "default_room": str(foreign_room.pk), "round_robin_weight": "0",
    }  # fmt: skip

    response = admin_post(admin_client(), f"{CONSOLE}/clinicians/new", values)

    html = response.content.decode()
    summary = html.split("error-summary", 1)[1].split("</ul>", 1)[0]
    assert response.status_code == 422
    assert WEIGHT_MESSAGE in html and ROOM_MESSAGE in html
    assert len(re.findall(r"<li><a href=", summary)) == 2
    assert not ClinicianProfile.objects.exists()
