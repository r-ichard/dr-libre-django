from pathlib import Path

from django.core.management.base import BaseCommand

from scheduling.data_model_document import render_data_model_document

DOCUMENT = Path(__file__).resolve().parents[3] / "doc" / "data-model.md"


class Command(BaseCommand):
    help = "Write doc/data-model.md from the models."

    def handle(self, *args: object, **options: object) -> None:
        DOCUMENT.write_text(render_data_model_document())
