#!/bin/sh
# Last gates of a pipeline run: the two that take minutes, which stages and reviewers skipped
# (tasks 24, 24c). A script runs them, so a run cannot end approved while either fails.
set -eu
# After a rewind this stage starts in a new sandbox, where the setup stage never ran.
command -v uv >/dev/null 2>&1 || make setup

make mutate
if grep -q '^fhir-validate:' Makefile; then
    make fhir-validate
fi
