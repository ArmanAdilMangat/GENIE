#!/usr/bin/env python3
"""Parse every .py file in the repository and fail on the first syntax error.

Most of the firmware is MicroPython, so it cannot be imported on a desktop
(`machine`, `espnow`, `micropython.viper`). It is still valid Python syntax,
and a file that does not even parse is the cheapest fault to catch before it
reaches a board.
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
bad = 0
count = 0
for path in sorted(ROOT.rglob("*.py")):
    if ".git" in path.parts:
        continue
    count += 1
    try:
        ast.parse(path.read_text(encoding="utf-8"), str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        bad += 1
        print("FAIL  %s: %s" % (path.relative_to(ROOT), exc))
print("%d files parsed, %d failed" % (count, bad))
sys.exit(1 if bad else 0)
