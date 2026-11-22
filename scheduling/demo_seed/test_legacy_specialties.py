"""Task 20, item 15: the seed touches only the five `demo-<code>` specialties it once made."""

import pytest

from scheduling.demo_seed import catalogue
from scheduling.demo_seed.seed_support import run_seed, seed_environment
from scheduling.models import ClinicianProfile, Specialty
from scheduling.models.builders import make

pytestmark = pytest.mark.django_db

__all__ = ["seed_environment"]


def returns_the_admin_made_specialty_when_its_code_starts_with_demo(
    seed_environment: None,
) -> None:
    mine = make("Specialty", code="demo-orthopaedics-extra")

    run_seed()

    assert Specialty.objects.filter(pk=mine.pk).exists()


def returns_one_set_and_no_lost_clinician_when_old_and_new_codes_both_hold_clinicians(
    seed_environment: None,
) -> None:
    run_seed()
    new = Specialty.objects.get(code="cardiology")
    legacy = make("Specialty", code="demo-cardiology")
    stranded = ClinicianProfile.objects.get(pk=make("ClinicianProfile", specialty=legacy).pk)
    seeded_before = ClinicianProfile.objects.filter(specialty=new).count()

    run_seed()

    assert not Specialty.objects.filter(code="demo-cardiology").exists()
    assert Specialty.objects.filter(code="cardiology").count() == 1
    stranded.refresh_from_db()
    assert stranded.specialty.code == "cardiology"
    assert (
        ClinicianProfile.objects.filter(specialty__code="cardiology").count() == seeded_before + 1
    )


def returns_the_legacy_clinicians_on_the_new_code_when_only_the_old_code_exists(
    seed_environment: None,
) -> None:
    legacy = make("Specialty", code="demo-dermatology")
    clinician = ClinicianProfile.objects.get(pk=make("ClinicianProfile", specialty=legacy).pk)

    run_seed()

    clinician.refresh_from_db()
    assert clinician.specialty.code == "dermatology"
    assert not Specialty.objects.filter(code="demo-dermatology").exists()


def returns_no_new_specialty_row_when_the_seed_runs_a_second_time(seed_environment: None) -> None:
    run_seed()
    before = sorted(Specialty.objects.values_list("code", flat=True))

    run_seed()

    assert sorted(Specialty.objects.values_list("code", flat=True)) == before
    assert len(before) >= len(catalogue.SPECIALTIES)
