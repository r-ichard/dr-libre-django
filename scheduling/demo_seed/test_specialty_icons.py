"""Task 19 item 19: every demo specialty shows its vendored icon, and every icon is used."""

from pathlib import Path

import pytest
from django.conf import settings

from scheduling.demo_seed.catalogue import SPECIALTIES
from scheduling.demo_seed.seed_support import run_seed, seed_environment
from scheduling.domain.specialty_icons import FALLBACK_ICON, VENDORED_CODES, icon_file_for
from scheduling.models import ClinicianProfile, Specialty

__all__ = ["seed_environment"]

ICON_DIRECTORY = Path(settings.BASE_DIR) / "static" / "icons" / "specialties"


def _icon_codes_on_disk() -> set[str]:
    return {path.stem for path in ICON_DIRECTORY.glob("*.svg")} - {Path(FALLBACK_ICON).stem}


def returns_the_codes_of_the_vendored_icon_files_when_icons_are_listed() -> None:
    assert set(VENDORED_CODES) == _icon_codes_on_disk()


def returns_the_vendored_codes_when_the_seeded_specialty_codes_are_listed() -> None:
    assert {seed.code for seed in SPECIALTIES} == _icon_codes_on_disk()


@pytest.mark.parametrize("code", [seed.code for seed in SPECIALTIES])
def returns_a_vendored_icon_when_a_seeded_specialty_is_shown(code: str) -> None:
    assert icon_file_for(code) != FALLBACK_ICON


def _rename(specialty: Specialty, code: str) -> None:
    specialty.code = code
    specialty.save()


@pytest.mark.django_db
def returns_no_legacy_demo_specialty_when_the_database_is_seeded(seed_environment: None) -> None:
    run_seed()

    assert not Specialty.objects.filter(code__startswith="demo-").exists()


@pytest.mark.django_db
def returns_same_id_and_clinicians_when_a_legacy_demo_specialty_is_renamed_in_place(
    seed_environment: None,
) -> None:
    run_seed()
    cardiology = Specialty.objects.get(code="cardiology")
    attached = ClinicianProfile.objects.filter(specialty=cardiology).count()
    _rename(cardiology, "demo-cardiology")

    run_seed()

    renamed = Specialty.objects.get(code="cardiology")
    assert renamed.pk == cardiology.pk
    assert ClinicianProfile.objects.filter(specialty=renamed).count() == attached


@pytest.mark.django_db
def returns_five_specialties_when_a_database_holding_the_legacy_codes_is_seeded(
    seed_environment: None,
) -> None:
    run_seed()
    for specialty in Specialty.objects.all():
        _rename(specialty, f"demo-{specialty.code}")

    run_seed()

    assert sorted(Specialty.objects.values_list("code", flat=True)) == sorted(
        seed.code for seed in SPECIALTIES
    )


@pytest.mark.django_db
def returns_no_legacy_row_when_an_unreferenced_demo_specialty_is_seeded_over(
    seed_environment: None,
) -> None:
    run_seed()
    Specialty.objects.create(code="demo-retired", name="Retired", is_active=True)

    run_seed()

    assert not Specialty.objects.filter(code="demo-retired").exists()


@pytest.mark.django_db
def returns_the_referenced_demo_specialty_when_a_clinician_still_uses_it(
    seed_environment: None,
) -> None:
    run_seed()
    retired = Specialty.objects.create(code="demo-retired", name="Retired", is_active=True)
    profile = ClinicianProfile.objects.first()
    assert profile is not None
    ClinicianProfile.objects.filter(pk=profile.pk).update(
        specialty=retired, version=profile.version + 1
    )

    run_seed()

    assert Specialty.objects.filter(code="demo-retired").exists()
