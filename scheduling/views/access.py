from rest_framework.permissions import BasePermission
from rest_framework.request import Request


class DenyUnlessDeclared(BasePermission):
    """Default access rule: a view that declares no permission_classes refuses everyone."""

    def has_permission(self, request: Request, view: object) -> bool:
        return False
