"""Task 23, spec 15.1: a write body is checked as a FHIR resource of the URL's type and id before
any use case runs. The first element the server would not have produced is named."""

import re
from collections.abc import Mapping

from scheduling.domain.failure import Failure, FieldMessage, Result, Success

type Shape = type | Mapping[str, Shape] | list[Shape]

IF_MATCH_PATTERN = re.compile(r'(?:W/)?"(\d{1,9})"')
INSTANCE_ID_PATTERN = re.compile(r"[A-Za-z0-9\-.]{1,64}")


def exact_elements(body: object, shape: Shape, path: str) -> str | None:
    """None when every element is known and of the declared type, else its dotted name."""
    if isinstance(shape, Mapping):
        if not isinstance(body, dict):
            return path
        for name, value in body.items():
            inner = shape.get(name)
            if inner is None:
                return f"{path}.{name}"
            problem = exact_elements(value, inner, f"{path}.{name}")
            if problem is not None:
                return problem
        return None
    if isinstance(shape, list):
        if not isinstance(body, list):
            return path
        for item in body:
            problem = exact_elements(item, shape[0], path)
            if problem is not None:
                return problem
        return None
    return None if type(body) is shape else path


def identity_problem(
    body: dict[str, object], resource_type: str, identifier: str | None
) -> str | None:
    """The type must be the URL's; the id is the URL's on a replace and absent on a create."""
    if body.get("resourceType") != resource_type:
        return f"{resource_type}.resourceType"
    if body.get("id") != identifier:
        return f"{resource_type}.id"
    return None


def if_match_version(header: str | None) -> Result[int | None]:
    """No header or version 0: no condition (versions start at 1). `W/"3"` or `"3"`: version 3.
    Anything else cannot be a version."""
    if header is None:
        return Success(None)
    found = IF_MATCH_PATTERN.fullmatch(header.strip())
    if found is None:
        return Failure.invalid_input([FieldMessage("If-Match", "Use the ETag of the record.")])
    version = int(found.group(1))
    return Success(version or None)
