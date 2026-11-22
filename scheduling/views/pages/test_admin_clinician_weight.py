"""Task 27a, finding #33: the clinician form refuses a weight beyond its column."""

import pytest

from scheduling.models import ClinicianProfile, User
from scheduling.models.builders import make
from scheduling.views.pages.admin_support import admin_client, admin_post

pytestmark = pytest.mark.django_db

NEW_CLINICIAN = "/admin-console/clinicians/new"


def _form(weight: str) -> dict[str, str]:
    user = make("User", role="CLINICIAN")
    assert isinstance(user, User)
    return {
        "user": str(user.pk),
        "department": str(make("Department").pk),
        "specialty": str(make("Specialty").pk),
        "title": "Dr",
        "bio": "",
        "default_room": "",
        "round_robin_weight": weight,
    }


@pytest.mark.parametrize("weight", ["32768", "40000", "99999999999"])
def returns_422_naming_the_weight_when_weight_is_above_the_column(weight: str) -> None:
    response = admin_post(admin_client(), NEW_CLINICIAN, _form(weight))

    assert response.status_code == 422
    assert "Use a whole number of at most 32767." in response.content.decode()
    assert not ClinicianProfile.objects.exists()


def returns_303_and_saved_weight_when_weight_is_the_largest_smallint() -> None:
    response = admin_post(admin_client(), NEW_CLINICIAN, _form("32767"))

    assert response.status_code == 303
    assert ClinicianProfile.objects.get().round_robin_weight == 32767
