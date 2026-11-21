"""Section 12.3: what a view states about who may call it. A view that states nothing is closed."""

from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.request import Request

from scheduling.models import User
from scheduling.models.people import Role

type Declaration = list[type[BasePermission]]


class DenyUnlessDeclared(BasePermission):
    """Default access rule: a view that declares no permission_classes refuses everyone."""

    def has_permission(self, request: Request, view: object) -> bool:
        return False


class IsSignedIn(BasePermission):
    def has_permission(self, request: Request, view: object) -> bool:
        return isinstance(request.user, User)


def public() -> Declaration:
    return [AllowAny]


def signed_in() -> Declaration:
    return [IsSignedIn]


def roles(*allowed: Role) -> Declaration:
    class HasRole(BasePermission):
        def has_permission(self, request: Request, view: object) -> bool:
            user = request.user
            return isinstance(user, User) and user.role in allowed

    return [HasRole]


def signed_in_user(request: Request) -> User:
    """The actor for a use case: only ever the session's user, never a field of the body."""
    user = request.user
    if not isinstance(user, User):
        raise NotAuthenticatedError("signed_in_user needs a view declared signed_in or roles")
    return user


class NotAuthenticatedError(Exception):
    """A view asked for the signed-in user without declaring it: a broken invariant."""
