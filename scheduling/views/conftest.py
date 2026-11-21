import pytest
from django.test import Client


@pytest.fixture
def probe_client(settings: object) -> Client:
    settings.ROOT_URLCONF = "scheduling.views.probe_urls"  # type: ignore[attr-defined]
    return Client(raise_request_exception=False)
