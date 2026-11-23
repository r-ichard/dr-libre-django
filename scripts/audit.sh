#!/bin/sh
# Audits the packages pinned in uv.lock for known vulnerabilities; exits non-zero on one.
# Not part of `make test`: pip-audit queries PyPI's vulnerability service over the network.
set -eu
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
uv export --locked --no-emit-project --format requirements-txt >"$WORK/requirements.txt"
uv run pip-audit --require-hashes --disable-pip -r "$WORK/requirements.txt" --cache-dir "$WORK/cache"
