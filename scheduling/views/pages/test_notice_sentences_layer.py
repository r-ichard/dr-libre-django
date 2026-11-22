"""Section 8: the views layer formats sentences; it does not query the database."""

import ast
from pathlib import Path
from uuid import uuid4

import pytest

from scheduling.views.pages.notice_sentences import notice_sentence

SOURCE = Path(__file__).with_name("notice_sentences.py")


def returns_no_model_import_when_notice_sentences_is_read() -> None:
    imported: list[str] = []
    for node in ast.walk(ast.parse(SOURCE.read_text())):
        if isinstance(node, ast.ImportFrom):
            imported += [f"{node.module}.{alias.name}" for alias in node.names]
        elif isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]

    assert [name for name in imported if name.startswith("scheduling.models")] == []


@pytest.mark.django_db
def returns_the_generic_noun_when_the_deactivated_user_is_gone() -> None:
    assert notice_sentence("user_deactivated", str(uuid4()), "") == "Deactivated the user."
