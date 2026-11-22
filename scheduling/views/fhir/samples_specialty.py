"""Task 24b2: samples of the specialty list write: the whole-list body that adds, renames,
deactivates and removes one concept, the answer to a write, and the two refusals that change
nothing (a used specialty removed, a stale `If-Match`)."""

import json

from django.test import Client

from scheduling.domain.fhir_common import Resource
from scheduling.views.fhir.samples_staff import FHIR_JSON, SAMPLE_HOST, fetch_document

LIST_PATH = "/fhir/CodeSystem/specialty"
SAMPLE_CODE = "sample-new"


def specialty_documents(client: Client) -> dict[str, Resource]:
    current = fetch_document(client, LIST_PATH)
    concepts = list(current.get("concept", []))  # type: ignore[call-overload]
    first, rest = concepts[0], concepts[1:]
    added: Resource = {"code": SAMPLE_CODE, "display": "Sample specialty"}
    documents = {
        "CodeSystem-update-staff": _with(current, [*concepts, added]),
        "CodeSystem-rename-staff": _with(current, [{**first, "display": "Renamed"}, *rest]),
        "CodeSystem-deactivate-staff": _with(
            current,
            [{**first, "property": [{"code": "inactive", "valueBoolean": True}]}, *rest],
        ),
        "CodeSystem-remove-staff": _with(current, rest),
        "CodeSystem-answer-staff": _put(client, current),
    }
    # Every concept removed: the seed's clinicians use some, so the console's refusal answers
    # and nothing is applied.
    refusal = _put(client, _with(current, []))
    documents["CodeSystem-refusal-staff"] = refusal
    documents["CodeSystem-stale-staff"] = _put(client, current, 'W/"999999"')
    return documents


def _with(current: Resource, concepts: list[Resource]) -> Resource:
    return {**current, "concept": concepts, "count": len(concepts)}


def _put(client: Client, body: Resource, if_match: str | None = None) -> Resource:
    headers = {"If-Match": if_match} if if_match else {}
    response = client.put(
        LIST_PATH,
        json.dumps(body),
        content_type=FHIR_JSON,
        SERVER_NAME=SAMPLE_HOST,
        headers=headers,
    )
    answer = response.json()
    assert isinstance(answer, dict)  # noqa: S101
    return answer
