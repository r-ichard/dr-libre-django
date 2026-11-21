"""Enough of an address to recognise it, never the whole of it."""


def mask_email(address: str) -> str:
    local_part, _, domain = address.partition("@")
    visible = local_part[:1] if len(local_part) > 1 else ""
    return f"{visible}***@{domain}"
