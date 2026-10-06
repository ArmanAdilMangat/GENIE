#!/usr/bin/env python3
"""Check the two AIML files that carry every deterministic spoken answer.

Three properties, each of which has already gone wrong once in this project:

  1. Both files are well-formed XML. A comment containing "--" breaks the
     whole file and the kernel then answers nothing.
  2. No two categories share a pattern. A duplicate makes the matcher pick
     one arbitrarily and the wrong answer appears intermittently.
  3. Every <condition> has a default <li> (one with no value). That branch
     is what an `unknown` sensor state lands on, so a missing one would let
     a dead sensor produce silence or the wrong sentence.
"""
import pathlib
import sys
import xml.etree.ElementTree as ET

HOST = pathlib.Path(__file__).resolve().parent.parent / "host"
bad = 0
seen = {}
total = 0
conditions = 0
for name in ("relay.aiml", "sensor.aiml"):
    try:
        root = ET.parse(HOST / name).getroot()
    except ET.ParseError as exc:
        print("FAIL  %s is not well-formed XML: %s" % (name, exc))
        bad += 1
        continue
    n = 0
    for cat in root.iter("category"):
        pat = cat.find("pattern")
        if pat is None:
            print("FAIL  %s: a category has no pattern" % name)
            bad += 1
            continue
        key = " ".join("".join(pat.itertext()).upper().split())
        that = cat.find("that")
        if that is not None:
            key += " <that> " + " ".join("".join(that.itertext()).upper().split())
        n += 1
        if key in seen:
            print("FAIL  duplicate pattern %r in %s and %s" % (key, seen[key], name))
            bad += 1
        seen[key] = name
    for cond in root.iter("condition"):
        items = cond.findall("li")
        if not items:
            continue                      # single-value form, no branches
        conditions += 1
        if not any("value" not in li.attrib for li in items):
            print("FAIL  %s: <condition name=%r> has no default branch"
                  % (name, cond.attrib.get("name")))
            bad += 1
    print("%-12s %3d patterns" % (name, n))
    total += n
print("%d patterns, %d branching conditions, %d problems" % (total, conditions, bad))
sys.exit(1 if bad else 0)
