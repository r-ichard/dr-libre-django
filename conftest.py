from collections.abc import Generator

import pytest
from django.conf import settings as django_settings

from drlibre.collection_guard import uncollected_test_names


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, pytest.CollectReport, pytest.CollectReport]:
    report = yield
    if not isinstance(collector, pytest.Module):
        return report
    # A function matching no python_functions pattern looks like a test and never runs.
    # A collection error, unlike an exception in a hook, survives xdist workers.
    patterns = collector.config.getini("python_functions")
    names = uncollected_test_names(collector.obj, patterns)
    if names:
        report.outcome = "failed"
        report.longrepr = f"not collected and not private (prefix _): {', '.join(names)}"
    return report


@pytest.fixture(autouse=True)
def fast_password_hasher(request: pytest.FixtureRequest) -> None:
    # Production PBKDF2 costs ~1.5 s per demo seed; no test needs a slow hash. Skipped when
    # Django is not configured (guard subprocess runs), where the settings fixture would skip.
    if not django_settings.configured:
        return
    settings = request.getfixturevalue("settings")
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
