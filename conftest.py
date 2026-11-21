import pytest

from drlibre.collection_guard import uncollected_test_names


def pytest_collectstart(collector: pytest.Collector) -> None:
    # A function matching no python_functions pattern looks like a test and never runs.
    if not isinstance(collector, pytest.Module):
        return
    patterns = collector.config.getini("python_functions")
    names = uncollected_test_names(collector.obj, patterns)
    if names:
        raise pytest.UsageError(
            f"{collector.nodeid}: not collected and not private (prefix _): {', '.join(names)}"
        )
