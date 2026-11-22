"""Task 20, item 5: every refusal names what is wrong in words, with a status and a way back."""

import pytest
from django.test import RequestFactory

from scheduling.domain.failure import Failure
from scheduling.models import User
from scheduling.models.builders import make
from scheduling.views.pages.admin_refusal import admin_refused_page

pytestmark = pytest.mark.django_db

ROOM_WORDS = "The room is already in use then."
PATIENT_WORDS = "The patient has another appointment then."
CLINICIAN_WORDS = "The clinician is no longer free then."


@pytest.mark.parametrize(
    ("resource", "words"),
    [("room", ROOM_WORDS), ("patient", PATIENT_WORDS), ("clinician", CLINICIAN_WORDS)],
)
def returns_409_with_the_resource_words_when_a_resource_is_busy(resource: str, words: str) -> None:
    user = make("User", role="ADMIN")
    assert isinstance(user, User)
    request = RequestFactory().get("/admin-console/waitlist")

    response = admin_refused_page(
        request, user, Failure.conflict([resource]), ("/admin-console/waitlist", "Back")
    )

    assert response.status_code == 409
    assert words in response.content.decode()
