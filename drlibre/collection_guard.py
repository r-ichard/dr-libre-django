import fnmatch
import inspect
import types

PRIVATE_PREFIX = "_"


def uncollected_test_names(module: types.ModuleType, patterns: list[str]) -> list[str]:
    """Names of functions defined in module that pytest would silently never collect."""
    return [
        name
        for name, member in vars(module).items()
        if inspect.isfunction(member)
        and member.__module__ == module.__name__
        and not name.startswith(PRIVATE_PREFIX)
        and not any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
    ]
