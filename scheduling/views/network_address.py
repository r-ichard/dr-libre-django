"""The caller's network address is REMOTE_ADDR only: a forwarded header is written by the caller."""

from django.http import HttpRequest
from rest_framework.request import Request


def network_address(request: Request | HttpRequest) -> str:
    return str(request.META.get("REMOTE_ADDR", ""))
