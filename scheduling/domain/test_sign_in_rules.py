"""Section 12: the home a signed-in user lands on."""

import pytest

from scheduling.domain.sign_in_rules import Home, home_for
from scheduling.models.people import Role


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.ADMIN, "admin_console"),
        (Role.CLINICIAN, "clinician_workspace"),
        (Role.PATIENT, "patient_portal"),
    ],
)
def returns_home_of_the_role(role: Role, expected: str) -> None:
    assert home_for(role) == Home(expected)
