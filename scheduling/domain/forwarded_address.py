"""The caller's address behind a counted number of trusted proxies."""

from ipaddress import ip_address


def caller_address(remote_address: str, forwarded_for: str, trusted_proxies: int) -> str:
    """Each trusted proxy appends the address it saw, so the entry that many places from the
    right is the caller; anything missing or malformed falls back to the connection address."""
    if trusted_proxies < 1:
        return remote_address
    entries = [entry.strip() for entry in forwarded_for.split(",")]
    if len(entries) < trusted_proxies:
        return remote_address
    entry = entries[-trusted_proxies]
    try:
        return str(ip_address(entry))
    except ValueError:
        return remote_address
