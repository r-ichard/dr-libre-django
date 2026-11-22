"""Start-up refuses development values when DEBUG is off."""

PUBLISHED_SECRET_KEY = "development-only-not-a-secret"  # noqa: S105
PUBLISHED_DEMO_PASSWORD = "demo-password-published"  # noqa: S105


def startup_refusal(
    debug: bool, secret_key: str, allowed_hosts: list[str], demo_password: str
) -> str | None:
    """The message for the first unsafe value, or None."""
    if debug:
        return None
    if secret_key == PUBLISHED_SECRET_KEY:
        return "SECRET_KEY is the published development key; set a private one or turn DEBUG on"
    if not allowed_hosts:
        return "ALLOWED_HOSTS is empty; list the host names the product answers to"
    if demo_password == PUBLISHED_DEMO_PASSWORD:
        return "DEMO_PASSWORD is the published demo password; unset it or turn DEBUG on"
    return None
