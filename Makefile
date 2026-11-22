# Stack binding (CLAUDE.md). An unbound target prints "not configured", the sentinel
# scripts/red_gate.sh reads; task 01 replaces it with the real command.
UV_VERSION := 0.12.13
# uv installs into ~/.local/bin and fabro command nodes run a non-login shell.
export PATH := $(HOME)/.local/bin:$(PATH)

# DEBUG stays off in tests; start-up refuses the published development values then.
SAFE_ENV := SECRET_KEY=test-only-key-k7Qx9vT2mWp4Zr8LbN3cYd6HfJs1UaEg5XoVt0RiKwMq2PzBn DEMO_PASSWORD=

.PHONY: setup test lint gate mutate fhir-validate

setup:
	command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/$(UV_VERSION)/install.sh | sh
	uv sync --locked
	uv run --env-file .env.example python scripts/ensure_database.py

test:
	uv run --env-file .env.example python scripts/ensure_database.py
	$(SAFE_ENV) DB_NAME=drlibre_run_$$$$ uv run --env-file .env.example pytest -n auto --maxprocesses=8

lint:
	uv run ruff check .
	uv run ruff format --check .
	$(SAFE_ENV) uv run --env-file .env.example mypy .

# Conventions §4.1 comment cap and §7 escape hatches over every tracked file.
gate:
	git ls-files -z | xargs -0 python3 scripts/comment_cap.py --files
	git ls-files -z | xargs -0 uv run python scripts/size_cap.py
	sh scripts/escape_hatches.sh

mutate:
	rm -rf mutants
	$(SAFE_ENV) uv run --env-file .env.example mutmut run
	$(SAFE_ENV) uv run --env-file .env.example mutmut results > mutants/results.txt
	uv run python scripts/mutation_survivors.py mutants/results.txt

# Not part of `make test`: fetches a pinned HL7 validator and a Java runtime.
fhir-validate:
	sh scripts/fhir_validate.sh
