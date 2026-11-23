"""Section 16: a destructive route confirms first. A GET changes nothing; a POST without a
valid token, or from another site, answers 403 and changes nothing. Routes come from the URL
configuration by last segment, so a new one is covered."""

import pytest
from django.apps import apps
from django.test import Client

from scheduling.models.builders import make
from scheduling.views.pages.admin_record_kinds import KIND_VIEWS
from scheduling.views.pages.admin_support import admin_client
from scheduling.views.pages.browser_support import CSRF_COOKIE, OTHER_SITE_ORIGIN, SITE_ORIGIN
from scheduling.views.pages.page_walk_support import (
    World,
    client_for_route,
    make_world,
    page_routes,
    path_of,
)

pytestmark = pytest.mark.django_db

DESTROYING_WORDS = {"delete", "cancel", "deactivate", "revoke", "remove", "leave"}
MINIMUM_ROUTES = 10
VALID_TOKEN = "x" * 32
MODEL_OF_KIND = {"clinician": "ClinicianProfile"}


def _routes() -> list[str]:
    return [
        route for route in page_routes() if route.rstrip("/").split("/")[-1] in DESTROYING_WORDS
    ]


def _state() -> dict[str, list[tuple[str, str]]]:
    return {
        model.__name__: sorted(
            (str(row.pk), str(getattr(row, "status", "")) + str(getattr(row, "is_active", "")))
            for row in model._default_manager.all()
        )
        for model in apps.get_app_config("scheduling").get_models()
    }


def _world_and_routes() -> tuple[World, list[str]]:
    return make_world(), _routes()


def returns_enough_destructive_routes_when_the_url_configuration_is_listed() -> None:
    assert len(_routes()) >= MINIMUM_ROUTES


def returns_the_same_rows_and_status_when_a_destructive_route_is_got() -> None:
    world, routes = _world_and_routes()
    for route in routes:
        client = client_for_route(route, world)
        before = _state()

        client.get(path_of(route, world))

        assert _state() == before, route


def returns_the_same_rows_when_the_delete_page_of_a_removable_record_is_got() -> None:
    admin = admin_client()
    for kind, view in KIND_VIEWS.items():
        record = make(MODEL_OF_KIND.get(kind, kind.title().replace("_", "")))
        before = _state()

        answers = admin.get(f"{view.base_path}/{record.pk}/delete").status_code

        assert answers == 200, kind
        assert _state() == before, kind


def returns_403_and_changes_nothing_when_a_destructive_route_is_posted_without_a_valid_token() -> (
    None
):
    world, routes = _world_and_routes()
    for route in routes:
        client = _enforcing(client_for_route(route, world))
        before = _state()

        answers = _post(client, path_of(route, world), token="")

        assert answers == 403, route
        assert _state() == before, route


def returns_403_and_changes_nothing_when_a_destructive_route_is_posted_from_another_site() -> None:
    world, routes = _world_and_routes()
    for route in routes:
        client = _enforcing(client_for_route(route, world))
        before = _state()

        answers = _post(client, path_of(route, world), origin=OTHER_SITE_ORIGIN)

        assert answers == 403, route
        assert _state() == before, route


def _enforcing(client: Client) -> Client:
    client.handler.enforce_csrf_checks = True
    return client


def _post(client: Client, path: str, token: str = VALID_TOKEN, origin: str = SITE_ORIGIN) -> int:
    client.cookies[CSRF_COOKIE] = VALID_TOKEN
    data = {"csrfmiddlewaretoken": token} if token else {}
    return client.post(path, data, headers={"Origin": origin}).status_code
