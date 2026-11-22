"""Task 22a: one sample of everything /fhir can answer, as the public and as a staff token,
read through the real routes. `make fhir-validate` hands them to the HL7 validator and a test
walks them for empty values."""

import json
from pathlib import Path

from django.test import Client

from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_declaration import FHIR_RESOURCES
from scheduling.models import User
from scheduling.use_cases.api_tokens import issue_token
from scheduling.views.api_clients import fhir_client

SAMPLE_HOST = "localhost"
VIEWS = ("public", "staff")
MISSING_PATH = "/fhir/Organization/00000000-0000-0000-0000-000000000000"


def sample_documents(staff_user: User) -> dict[str, Resource]:
    """File name to JSON body. The staff user's token is created here and kept nowhere."""
    token = issue_token(staff_user, "fhir-samples").token
    documents: dict[str, Resource] = {}
    for view in VIEWS:
        client = fhir_client(token if view == "staff" else None)
        documents.update(_view_documents(client, view))
    return documents


def _view_documents(client: Client, view: str) -> dict[str, Resource]:
    def fetch(path: str) -> Resource:
        body: Resource = client.get(path, SERVER_NAME=SAMPLE_HOST).json()
        return body

    documents: dict[str, Resource] = {}
    for declaration in FHIR_RESOURCES:
        name = declaration.type
        bundle = fetch(f"/fhir/{name}")
        documents[f"{name}-search-{view}"] = bundle
        identifiers = [entry["resource"]["id"] for entry in bundle.get("entry", [])]  # type: ignore[attr-defined]
        if identifiers:
            documents[f"{name}-read-{view}"] = fetch(f"/fhir/{name}/{identifiers[0]}")
    include = "_include=PractitionerRole:practitioner&_include=PractitionerRole:organization"
    documents[f"PractitionerRole-include-{view}"] = fetch(f"/fhir/PractitionerRole?{include}")
    documents[f"metadata-{view}"] = fetch("/fhir/metadata")
    documents[f"OperationOutcome-{view}"] = fetch(MISSING_PATH)
    return documents


def write_samples(staff_user: User, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, body in sample_documents(staff_user).items():
        path = directory / f"{name}.json"
        path.write_text(json.dumps(body, indent=2))
        written.append(path)
    return written
