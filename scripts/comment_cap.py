#!/usr/bin/env python3
"""Comment-cap gate (conventions §4.1): no contiguous comment block over 255 characters.
Modes: --hook (Claude Code PreToolUse, tool JSON on stdin, exit 2 blocks), --files PATH...
(make gate and git pre-commit, exit 1 on violation), --self-test."""

import json
import pathlib
import re
import sys

CAP = 255
SKIP_SUFFIXES = {".md", ".mdx", ".txt", ".json", ".lock", ".svg", ".csv", ".html"}
# `--` counts only before whitespace: SQL comments yes, CSS custom properties `--name:` no.
LINE_MARKER = re.compile(r"^(//+|#+|--(?=\s|$)|;+)\s?")
# Graphviz files use // and /* */ only; `#id { ... }` inside a stylesheet string is code.
DOT_SUFFIXES = {".fabro", ".dot", ".gv"}
DOT_MARKER = re.compile(r"^(//+)\s?")
BLOCK_DELIMITERS = {"/*": "*/", "<!--": "-->", '"""': '"""', "'''": "'''"}
# Vendored skills are read-only third-party trees (conventions §13.1); never hand-edited.
VENDORED_PREFIXES = (".claude/skills/",)
LICENCE_WORDS = ("copyright", "spdx-license-identifier", "licensed under")


def main(argv):
    mode, *rest = argv or ["--help"]
    if mode == "--self-test":
        return self_test()
    if mode == "--hook":
        return hook_mode(rest)
    if mode == "--files":
        return files_mode(rest)
    print(__doc__)
    return 64


def hook_mode(rest):
    source = pathlib.Path(rest[0]).read_text() if rest else sys.stdin.read()
    tool_input = json.loads(source).get("tool_input", {})
    found = check(texts_from_tool_input(tool_input))
    if found:
        # Claude Code feeds stderr back to the agent when a hook exits 2.
        print("§4.1 comment cap: " + "; ".join(found), file=sys.stderr)
        return 2
    return 0


def files_mode(paths):
    entries = [(p, pathlib.Path(p).read_text(errors="replace")) for p in paths if pathlib.Path(p).is_file()]
    found = check(entries)
    if found:
        print("\n".join(found), file=sys.stderr)
        return 1
    return 0


def check(entries):
    found = []
    for name, text in entries:
        suffix = pathlib.Path(name).suffix.lower()
        if suffix in SKIP_SUFFIXES or name.startswith(VENDORED_PREFIXES):
            continue
        marker = DOT_MARKER if suffix in DOT_SUFFIXES else LINE_MARKER
        found += [f"{name}:{line}: comment block is {size} chars, cap is {CAP}" for line, size in violations(text, marker)]
    return found


def texts_from_tool_input(tool_input):
    path = tool_input.get("file_path", "")
    if "content" in tool_input:
        return [(path, tool_input["content"])]
    if "new_string" in tool_input:
        # shortcut: Edit is judged on new_string alone, a block that grows across
        # old context is missed; make gate catches it on the tracked file.
        return [(path, tool_input["new_string"])]
    if "patch" in tool_input:
        return patch_additions(tool_input["patch"])
    return []


def patch_additions(patch):
    files, name, added = [], "", []
    for raw in patch.splitlines():
        if raw.startswith("*** ") and " File: " in raw:
            if added:
                files.append((name, "\n".join(added)))
            name, added = raw.split(" File: ", 1)[1].strip(), []
        elif raw.startswith("+") and not raw.startswith("+++"):
            added.append(raw[1:])
    if added:
        files.append((name, "\n".join(added)))
    return files


def violations(text, marker=LINE_MARKER):
    found = []
    for line, pieces in comment_blocks(text, marker):
        body = " ".join(piece for piece in pieces if piece)
        if len(body) > CAP and not any(word in body.lower() for word in LICENCE_WORDS):
            found.append((line, len(body)))
    return found


def comment_blocks(text, marker=LINE_MARKER):
    blocks, current, closer = [], None, None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if closer is not None:
            inner, found, _ = line.partition(closer)
            current[1].append(inner.strip(" *"))
            closer = None if found else closer
            continue
        opener = next((o for o in BLOCK_DELIMITERS if line.startswith(o)), None)
        if opener is not None:
            inner, found, _ = line[len(opener):].partition(BLOCK_DELIMITERS[opener])
            current = current or [number, []]
            current[1].append(inner.strip(" *"))
            closer = None if found else BLOCK_DELIMITERS[opener]
            continue
        matched = marker.match(line)
        if matched and not line.startswith("#!"):
            current = current or [number, []]
            current[1].append(line[matched.end():].strip())
            continue
        if current:
            blocks.append(tuple(current))
            current = None
    if current:
        blocks.append(tuple(current))
    return blocks


def self_test():
    long = "x" * 300
    assert violations("// short\nreturn 1\n") == []
    assert violations("# " + long) == [(1, 300)]
    assert violations("// a\ncode()\n// b\n") == []
    assert violations("/*\n * " + long + "\n */\n") == [(1, 300)]
    assert violations('"""\n' + long + '\n"""\n') == [(1, 300)]
    assert violations("/* Copyright 2026 " + long + " */") == []
    assert violations("#!" + long) == []
    assert violations(":root {\n  --color-a: #fff;\n  --color-b: " + long + ";\n}\n") == []
    assert violations("-- " + long) == [(1, 300)]
    assert check([("w.fabro", "#review { model: " + long + "; }\n")]) == []
    assert check([("w.fabro", "// " + long)]) != []
    assert check([("notes.md", "# " + long)]) == []
    assert check([(".claude/skills/x/run", "# " + long)]) == []
    assert check(patch_additions("*** Update File: a.py\n@@\n+# " + long + "\n-old\n")) != []
    assert check(texts_from_tool_input({"file_path": "a.py", "new_string": "# ok"})) == []
    print("comment_cap self-test ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
