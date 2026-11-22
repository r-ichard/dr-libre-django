"""The caller's network address: REMOTE_ADDR, or the forwarded entry a trusted proxy wrote."""

from django.conf import settings
from django.http import HttpRequest
from rest_framework.request import Request

from scheduling.domain.forwarded_address import caller_address


def network_address(request: Request | HttpRequest) -> str:
    return caller_address(
        str(request.META.get("REMOTE_ADDR", "")),
        str(request.META.get("HTTP_X_FORWARDED_FOR", "")),
        settings.TRUSTED_PROXY_COUNT,
    )
