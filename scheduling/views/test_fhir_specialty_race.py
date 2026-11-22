"""Task 24b2, point 4: two admins write the specialty list at the same moment, each in its own
connection and transaction. The list holds what one of them sent, never a mix."""

import json
from threading import Barrier, Thread

import pytest
from django.db import connections

from scheduling.models import Specialty
from scheduling.views import clock
from scheduling.views.fhir_specialty_support import LIST_PATH, concept, stored, with_concepts
from scheduling.views.fhir_test_support import NOW, get, send, token_of

pytestmark = pytest.mark.django_db(transaction=True)

ATTEMPTS = range(10)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _race(bodies: list[dict[str, object]], tokens: list[str], **headers: str) -> list[int]:
    barrier = Barrier(len(bodies))
    statuses: list[int] = []

    def worker(body: dict[str, object], token: str) -> None:
        try:
            barrier.wait()
            statuses.append(send("put", LIST_PATH, body, token, **headers).status_code)
        finally:
            connections.close_all()

    threads = [Thread(target=worker, args=pair) for pair in zip(bodies, tokens, strict=True)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return statuses


def _names() -> set[str]:
    return set(Specialty.objects.values_list("name", flat=True))


@pytest.mark.parametrize("attempt", ATTEMPTS)
def returns_200_for_one_and_412_for_the_other_when_two_admins_write_with_the_same_if_match(
    committed_rows: None, attempt: int
) -> None:
    stored("cardio", "Cardiology")
    tokens = [token_of(role="ADMIN"), token_of(role="ADMIN")]
    etag = get(LIST_PATH, tokens[0])["ETag"]
    first = with_concepts(tokens[0], concept("cardio", "Heart care"))
    second = with_concepts(
        tokens[0], concept("cardio", "Cardiac unit"), concept("neuro", "Neurology")
    )

    statuses = _race([first, second], tokens, **{"If-Match": etag})

    assert sorted(statuses) == [200, 412], json.dumps(statuses)
    assert _names() in ({"Heart care"}, {"Cardiac unit", "Neurology"})


@pytest.mark.parametrize("attempt", ATTEMPTS)
def returns_200_for_both_and_holds_one_whole_body_when_two_admins_write_without_if_match(
    committed_rows: None, attempt: int
) -> None:
    stored("cardio", "Cardiology")
    tokens = [token_of(role="ADMIN"), token_of(role="ADMIN")]
    first = with_concepts(tokens[0], concept("cardio", "Heart care"))
    second = with_concepts(
        tokens[0], concept("derma", "Dermatology"), concept("neuro", "Neurology")
    )

    statuses = _race([first, second], tokens)

    assert statuses == [200, 200], json.dumps(statuses)
    assert _names() in ({"Heart care"}, {"Dermatology", "Neurology"})
