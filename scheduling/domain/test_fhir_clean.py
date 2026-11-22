"""Task 22a: no FHIR resource carries an empty array, object or string, or a null."""

import importlib

from scheduling.domain.failure import Failure, Success
from scheduling.domain.fhir_capability import capability_statement
from scheduling.domain.fhir_declaration import FHIR_RESOURCES, declaration_for
from scheduling.domain.fhir_search import parse_search


def _without_empty(value: object) -> object:
    return importlib.import_module("scheduling.domain.fhir_clean").without_empty(value)


def returns_value_without_none_empty_string_list_and_object_when_nested_deeply() -> None:
    value: dict[str, object] = {
        "a": None,
        "b": "",
        "c": [],
        "d": {},
        "e": {"f": [{"g": ""}, {"h": "kept"}]},
    }

    assert _without_empty(value) == {"e": {"f": [{"h": "kept"}]}}


def returns_object_without_key_when_its_children_all_clean_away() -> None:
    assert _without_empty({"keep": 1, "gone": {"x": [None, ""]}}) == {"keep": 1}


def returns_false_zero_and_text_kept_when_cleaned_zero_and_nonempty_text() -> None:
    assert _without_empty({"a": False, "b": 0, "c": " ", "d": [0, False]}) == {
        "a": False,
        "b": 0,
        "c": " ",
        "d": [0, False],
    }


def returns_list_without_empty_items_in_order_when_cleaned() -> None:
    assert _without_empty(["b", "", None, "a", [], {}]) == ["b", "a"]


def returns_new_value_and_leaves_input_when_cleaned() -> None:
    value: dict[str, object] = {"a": [{"b": ""}], "c": 1}

    _without_empty(value)

    assert value == {"a": [{"b": ""}], "c": 1}


def returns_description_and_implementation_url_when_capability_statement_built() -> None:
    statement = capability_statement(FHIR_RESOURCES)

    assert statement["description"]
    implementation = statement["implementation"]
    assert isinstance(implementation, dict)
    assert str(implementation["url"]).startswith("http")


def returns_both_includes_when_include_repeated() -> None:
    declaration = declaration_for("PractitionerRole")
    assert declaration is not None
    both = ["PractitionerRole:practitioner", "PractitionerRole:organization"]

    result = parse_search(declaration, {"_include": both})

    assert isinstance(result, Success)
    assert result.value.include == tuple(both)


def returns_one_include_when_same_include_repeated() -> None:
    declaration = declaration_for("PractitionerRole")
    assert declaration is not None
    same = ["PractitionerRole:practitioner"] * 2

    result = parse_search(declaration, {"_include": same})

    assert isinstance(result, Success)
    assert result.value.include == ("PractitionerRole:practitioner",)


def returns_refusal_naming_parameter_when_filter_repeated() -> None:
    declaration = declaration_for("Organization")
    assert declaration is not None

    result = parse_search(declaration, {"name": ["a", "b"]})

    assert isinstance(result, Failure)
    assert result.details == {
        "fields": [{"field": "name", "message": "A parameter may be given once."}]
    }


def returns_refusal_when_repeated_include_is_undeclared() -> None:
    declaration = declaration_for("PractitionerRole")
    assert declaration is not None

    result = parse_search(declaration, {"_include": ["PractitionerRole:practitioner", "x:y"]})

    assert isinstance(result, Failure)
    assert result.details == {
        "fields": [{"field": "_include", "message": "The value cannot be read."}]
    }
