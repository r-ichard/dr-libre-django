#!/bin/sh
# Task 22a: seed a throwaway database, sample everything /fhir answers, run the HL7 validator.
# Fails on any error. Validator and Java are fetched here, not by `make setup`; the jar is pinned.
set -eu

VALIDATOR_VERSION=7.0.6
VALIDATOR_SHA256=2686590539f0b3ba7683149b25d78249f6886c04e2c326e884c5049d8947df89
VALIDATOR_URL="https://github.com/hapifhir/org.hl7.fhir.core/releases/download/$VALIDATOR_VERSION/validator_cli.jar"
CACHE=".cache/fhir-validator/$VALIDATOR_VERSION"
JAR="$CACHE/validator_cli.jar"
SAMPLES=$(mktemp -d)
DB_NAME="drlibre_validate_$$"
export DB_NAME
cleanup() {
  rm -rf "$SAMPLES"
  uv run --env-file .env.example python scripts/drop_database.py || true
}
trap cleanup EXIT

if ! command -v java >/dev/null; then
  apt-get update -qq && apt-get install -y -qq default-jre-headless
fi

mkdir -p "$CACHE"
if ! { [ -f "$JAR" ] && echo "$VALIDATOR_SHA256  $JAR" | sha256sum -c - >/dev/null 2>&1; }; then
  curl -fsSL -o "$JAR" "$VALIDATOR_URL"
  echo "$VALIDATOR_SHA256  $JAR" | sha256sum -c -
fi

export DEBUG=true
uv run --env-file .env.example python scripts/ensure_database.py
uv run --env-file .env.example python manage.py migrate --noinput -v 0
uv run --env-file .env.example python manage.py seed_demo >/dev/null
uv run --env-file .env.example python manage.py fhir_samples "$SAMPLES"
java -jar "$JAR" "$SAMPLES" -version 4.0.1 -tx n/a -extension any
