#!/bin/sh
# Last gates of a pipeline run: the two that take minutes, which stages and reviewers skipped
# (tasks 24, 24c). A script runs them, so a run cannot end approved while either fails.
set -eu

make mutate
if grep -q '^fhir-validate:' Makefile; then
    make fhir-validate
fi
