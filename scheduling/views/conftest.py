import pytest
from django.test import Client

from scheduling.views.api_clients import browser_api_client


@pytest.fixture
def probe_client(settings: object) -> Client:
    settings.ROOT_URLCONF = "scheduling.views.probe_urls"  # type: ignore[attr-defined]
    return browser_api_client(raise_request_exception=False)
