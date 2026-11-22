"""Task 23, spec 15.4: who is asking through /fhir. The viewer decides what a read may show; the
user, when a token named one, decides whose records a write or a patient read may touch."""

from dataclasses import dataclass

from scheduling.domain.vocabulary import Role
from scheduling.models import User
from scheduling.use_cases.fhir_reads import Viewer


@dataclass(frozen=True)
class Caller:
    viewer: Viewer
    user: User | None

    @property
    def role(self) -> Role | None:
        return Role(self.user.role) if self.user is not None else None


PUBLIC_CALLER = Caller(Viewer.PUBLIC, None)
