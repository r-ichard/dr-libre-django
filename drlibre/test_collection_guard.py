import textwrap
import types

from drlibre.collection_guard import uncollected_test_names

PATTERNS = ["returns_*", "raises_*", "rejects_*"]


def _build_module(source: str) -> types.ModuleType:
    module = types.ModuleType("example_tests")
    # Test-owned literal source, the cheapest way to build a module with chosen functions.
    exec(textwrap.dedent(source), module.__dict__)  # noqa: S102
    return module


def returns_names_of_functions_matching_no_pattern_when_module_has_unmatched_function() -> None:
    module = _build_module(
        """
        def checks_x(): ...
        def returns_y(): ...
        """
    )

    assert uncollected_test_names(module, PATTERNS) == ["checks_x"]


def returns_nothing_when_unmatched_function_is_private_helper() -> None:
    module = _build_module("def _build_x(): ...")

    assert uncollected_test_names(module, PATTERNS) == []


def returns_nothing_when_function_matches_rejects_pattern() -> None:
    module = _build_module("def rejects_x(): ...")

    assert uncollected_test_names(module, PATTERNS) == []


def returns_nothing_when_function_is_imported() -> None:
    module = _build_module("from os.path import join")

    assert uncollected_test_names(module, PATTERNS) == []


def returns_nothing_when_function_is_a_fixture() -> None:
    module = _build_module(
        """
        import pytest

        @pytest.fixture
        def inbox(): ...
        """
    )

    assert uncollected_test_names(module, PATTERNS) == []


def returns_nothing_when_name_is_not_a_function() -> None:
    module = _build_module("LIMIT = 3")

    assert uncollected_test_names(module, PATTERNS) == []


def returns_nothing_when_name_is_a_class() -> None:
    module = _build_module("class Helper: ...")

    assert uncollected_test_names(module, PATTERNS) == []
