"""Task 24c: request bodies and helpers the PractitionerRole write tests share."""

from datetime import datetime
from uuid import UUID

from scheduling.domain.fhir_common import SPECIALTY_SYSTEM
from scheduling.models import ClinicianProfile, Department, Room, Specialty, User
from scheduling.models.builders import make
from scheduling.views.fhir_test_support import extension, get


def new_role_body(
    user: User, department: Department, specialty: Specialty, room: Room | None = None
) -> dict[str, object]:
    body: dict[str, object] = {
        "resourceType": "PractitionerRole",
        "practitioner": {"reference": f"Practitioner/{user.pk}"},
        "organization": {"reference": f"Organization/{department.pk}"},
        "specialty": [{"coding": [{"system": SPECIALTY_SYSTEM, "code": specialty.code}]}],
        "extension": [
            extension("role-bio", valueString="Heart rhythm."),
            extension("role-round-robin-weight", valueInteger=3),
        ],
    }
    if room is not None:
        body["location"] = [{"reference": f"Location/{room.pk}"}]
    return body


def stored_role(token: str, profile: ClinicianProfile) -> dict[str, object]:
    body = get(f"/fhir/PractitionerRole/{profile.pk}", token).json()
    assert isinstance(body, dict)  # noqa: S101
    return body


def element_names(response_body: dict[str, object]) -> list[str]:
    issues = response_body["issue"]
    assert isinstance(issues, list)  # noqa: S101
    return [name for issue in issues for name in issue.get("expression", [])]


def period(start: datetime, end: datetime, description: str = "") -> dict[str, object]:
    found: dict[str, object] = {"during": {"start": start.isoformat(), "end": end.isoformat()}}
    if description:
        found["description"] = description
    return found


def profile_id(role: dict[str, object]) -> UUID:
    return UUID(str(role["id"]))


def new_profile_inputs() -> tuple[User, Department, Specialty]:
    user = make("User", role="CLINICIAN")
    department = make("Department")
    specialty = make("Specialty")
    assert isinstance(user, User)  # noqa: S101
    assert isinstance(department, Department)  # noqa: S101
    assert isinstance(specialty, Specialty)  # noqa: S101
    return user, department, specialty
