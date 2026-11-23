MAXIMUM_TEST_SECONDS = 60


def over_limit_message(nodeid: str, phase: str, seconds: float, limit: float) -> str | None:
    # The limit is a parameter so the tests can pass literal values instead of sleeping.
    if seconds <= limit:
        return None
    return (
        f"{nodeid}: {phase} took {seconds:.1f} s, over the {limit:g} s limit (MAXIMUM_TEST_SECONDS)"
    )
