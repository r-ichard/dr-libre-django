"""Sections 7 and 12: secrets are stored as hashes only; no column could hold the secret."""

import pytest
from django.db.models import Field

from scheduling.models.builders import SIXTY_FOUR, make, model_class

pytestmark = pytest.mark.django_db

SECRET_MODELS = {
    "Session": "token_hash",
    "VerificationCode": "code_hash",
    "SignInLink": "token_hash",
    "ApiClient": "token_hash",
}
FORBIDDEN_NAMES = {"token", "code", "secret", "key", "link", "url", "password"}


@pytest.mark.parametrize(("model_name", "hash_field"), SECRET_MODELS.items())
def returns_hash_column_when_secret_model_is_inspected(model_name: str, hash_field: str) -> None:
    field_names = [field.name for field in model_class(model_name)._meta.get_fields()]

    assert hash_field in field_names


@pytest.mark.parametrize("model_name", SECRET_MODELS)
def returns_no_column_that_could_hold_the_secret_when_secret_model_is_inspected(
    model_name: str,
) -> None:
    field_names = [field.name for field in model_class(model_name)._meta.get_fields()]

    holders = [
        name
        for name in field_names
        if (name in FORBIDDEN_NAMES or any(word in name for word in FORBIDDEN_NAMES))
        and not name.endswith("_hash")
        and name not in {"user", "patient"}
    ]
    assert holders == []


@pytest.mark.parametrize(("model_name", "hash_field"), SECRET_MODELS.items())
def returns_hash_column_limited_to_64_characters_when_secret_model_is_inspected(
    model_name: str, hash_field: str
) -> None:
    field = model_class(model_name)._meta.get_field(hash_field)

    assert _field_attribute(field, "max_length") == 64


def _field_attribute(field: object, attribute: str) -> object:
    assert isinstance(field, Field)
    return getattr(field, attribute)


def returns_link_open_by_default_when_sign_in_link_is_created() -> None:
    from scheduling.models.builders import make  # noqa: PLC0415

    link = make("SignInLink")

    assert link.cancelled_at is None  # type: ignore[attr-defined]


def returns_refusal_when_two_api_clients_share_a_token_hash() -> None:
    from scheduling.models.builders import refuses  # noqa: PLC0415

    make("ApiClient", token_hash=SIXTY_FOUR)

    refuses("ApiClient", token_hash=SIXTY_FOUR)


def returns_refusal_when_api_client_name_is_blank() -> None:
    from scheduling.models.builders import refuses  # noqa: PLC0415

    refuses("ApiClient", name="")
