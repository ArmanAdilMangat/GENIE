#!/usr/bin/env python3
"""Fail if a credential or a real phone number is about to be committed.

The firmware and the host both carry a Wi-Fi password and an emergency
contact list. In this repository those are placeholders; the real values
live in git-ignored files (wifi_cfg.py, settings.py) or are edited locally
in host/config.py and not committed.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEXT = {".py", ".md", ".txt", ".aiml", ".json", ".yml", ".yaml", ".ino", ".h", ".cpp", ".ini"}
ALLOWED_NUMBERS = {"+920000000000", "+923001234567"}       # placeholder, documentation example
PASSWORD = re.compile(r'\b(?:WIFI_)?PASSWORD\s*=\s*"([^"]*)"')
PHONE = re.compile(r"\+92\d{10}\b")

bad = 0
for path in sorted(ROOT.rglob("*")):
    if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in TEXT:
        continue
    if "legacy" in path.parts or path.name == "check_secrets.py":
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for i, line in enumerate(text.splitlines(), 1):
        for m in PASSWORD.finditer(line):
            if m.group(1) not in ("change-me", "", "YOUR_PASSWORD"):
                print("FAIL  %s:%d  literal Wi-Fi password" % (path.relative_to(ROOT), i))
                bad += 1
        for m in PHONE.finditer(line):
            if m.group(0) not in ALLOWED_NUMBERS:
                print("FAIL  %s:%d  phone number" % (path.relative_to(ROOT), i))
                bad += 1
print("%d problems" % bad)
sys.exit(1 if bad else 0)
