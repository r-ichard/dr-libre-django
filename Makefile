# Stack binding (CLAUDE.md). An unbound target prints "not configured", the sentinel
# scripts/red_gate.sh reads; task 01 replaces it with the real command.
UV_VERSION := 0.12.13
# uv installs into ~/.local/bin and fabro command nodes run a non-login shell.
export PATH := $(HOME)/.local/bin:$(PATH)

.PHONY: setup test lint gate mutate

setup:
	command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/$(UV_VERSION)/install.sh | sh
	[ ! -f uv.lock ] || uv sync --locked

test:
	@echo "make test: not configured" >&2; exit 1

lint:
	@echo "make lint: not configured" >&2; exit 1

# Conventions §4.1 comment cap and §7 escape hatches over every tracked file.
gate:
	git ls-files -z | xargs -0 python3 scripts/comment_cap.py --files
	sh scripts/escape_hatches.sh

mutate:
	@echo "make mutate: not configured" >&2; exit 1
