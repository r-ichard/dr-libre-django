# Stack binding (CLAUDE.md). An unbound target prints "not configured", the sentinel
# scripts/red_gate.sh reads; task 01 replaces it with the real command.
UV_VERSION := 0.12.13
# uv installs into ~/.local/bin and fabro command nodes run a non-login shell.
export PATH := $(HOME)/.local/bin:$(PATH)

.PHONY: setup test lint gate mutate

setup:
	command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/$(UV_VERSION)/install.sh | sh
	uv sync --locked
	uv run --env-file .env.example python scripts/ensure_database.py

test:
	uv run --env-file .env.example python scripts/ensure_database.py
	DB_NAME=drlibre_run_$$$$ uv run --env-file .env.example pytest -n auto --maxprocesses=4

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run --env-file .env.example mypy .

# Conventions §4.1 comment cap and §7 escape hatches over every tracked file.
gate:
	git ls-files -z | xargs -0 python3 scripts/comment_cap.py --files
	sh scripts/escape_hatches.sh

mutate:
	@echo "make mutate: not configured" >&2; exit 1
