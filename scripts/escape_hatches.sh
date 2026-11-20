#!/bin/sh
# Conventions §7 gate: type and lint escape hatches are defects, not style. Exit 1 when a
# tracked Python file carries one. Allowed: `# type: ignore[code]` and `# noqa: CODE`.
pattern='# type: ?ignore($|[^[])|# pyright: ?ignore($|[^[])|# noqa($|[^:])|import .*\bAny\b|\btyping\.Any\b|import .*\bcast\b|\btyping\.cast\b'

if [ "${1:-}" = "--self-test" ]; then
  caught=$(printf '%s\n' 'value = load()  # type: ignore' 'import os  # noqa' 'from typing import Any' \
    'count = typing.cast(int, raw)' 'from typing import Protocol, cast' | grep -cE "$pattern")
  passed=$(printf '%s\n' 'value = load()  # type: ignore[assignment]' 'import os  # noqa: F401' \
    '# Any error here is logged' 'broadcast(message)' 'from django.db.models.functions import Cast' | grep -cE "$pattern")
  [ "$caught" = 5 ] && [ "$passed" = 0 ] && echo "escape hatch self-test ok" && exit 0
  echo "escape hatch self-test failed: caught $caught of 5, wrongly flagged $passed" >&2
  exit 1
fi

# Django migrations are generated code.
hits=$(git ls-files -z -- '*.py' | grep -zv '/migrations/' | xargs -0 grep -nHE "$pattern" 2>/dev/null || true)
if [ -n "$hits" ]; then
  echo "$hits" >&2
  echo "escape hatches found (§7). Use a precise type, a schema, or a typed adapter." >&2
  exit 1
fi
echo "escape hatch gate: clean"
