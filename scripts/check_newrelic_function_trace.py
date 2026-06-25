#!/usr/bin/env python
"""Verify config/newrelic.ini transaction_tracer.function_trace entries.

Every entry must resolve to a real symbol in the repo. New Relic silently
drops traces for renamed/missing symbols with no error, so a stale entry
can hide useful telemetry indefinitely. This guard fails CI when an
entry stops resolving.

Uses AST instead of import so no Django bootstrap is required.
"""
from __future__ import annotations

import ast
import configparser
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
INI_PATH = REPO_ROOT / "config" / "newrelic.ini"


def find_symbol(tree: ast.Module, dotted: str) -> bool:
    parts = dotted.split(".")
    nodes: list[ast.stmt] = list(tree.body)
    for part in parts:
        match: ast.stmt | None = None
        for node in nodes:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == part:
                match = node
                break
        if match is None:
            return False
        nodes = list(match.body) if isinstance(match, ast.ClassDef) else []
    return True


def main() -> int:
    cfg = configparser.ConfigParser()
    cfg.read(INI_PATH)
    raw = cfg.get("newrelic", "transaction_tracer.function_trace", fallback="")
    entries = [line.strip() for line in raw.splitlines() if line.strip()]

    if not entries:
        print("No transaction_tracer.function_trace entries to check.")
        return 0

    missing: list[tuple[str, str]] = []
    for entry in entries:
        module, _, dotted = entry.partition(":")
        if not dotted:
            missing.append((entry, "expected 'module:symbol' form"))
            continue
        path = REPO_ROOT / pathlib.Path(*module.split(".")).with_suffix(".py")
        if not path.exists():
            missing.append((entry, f"module file not found: {path.relative_to(REPO_ROOT)}"))
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as e:
            missing.append((entry, f"syntax error in {path.relative_to(REPO_ROOT)}: {e}"))
            continue
        if not find_symbol(tree, dotted):
            missing.append((entry, f"symbol '{dotted}' not found in {path.relative_to(REPO_ROOT)}"))

    if missing:
        print("ERROR: newrelic.ini function_trace entries that do not resolve:", file=sys.stderr)
        for entry, reason in missing:
            print(f"  - {entry}\n      {reason}", file=sys.stderr)
        print(
            "\nFix: update config/newrelic.ini to point at the real symbol, " "or remove the entry.",
            file=sys.stderr,
        )
        return 1

    print(f"All {len(entries)} function_trace entries resolved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
