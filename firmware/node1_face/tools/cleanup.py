"""
cleanup.py - work out what is actually on the ESP32, and what to delete.

Old copies of eyes.py, genie_live.py, onebutton.py and MENU.py are the real
hazard here. MicroPython imports whatever it finds first on the device root,
so a stale eyes.py shadows the new one and you spend an hour debugging code
that is not running.

    import cleanup
    cleanup.audit()          # SAFE. Lists everything, marks what to delete.
    cleanup.purge()          # actually deletes. Asks first, per file.
    cleanup.purge(force=1)   # no prompts. Read the audit before you do this.

Nothing is deleted unless you call purge(). audit() only ever reads.
"""

import os

# what the running GENIE face needs, and nothing more
KEEP = (
    "boot.py",
    "main.py",
    "pins.py",
    "ili9341_par.py",
    "eyes.py",          # RoboEyes - the ONLY face module
    "sensors.py",
    "genie_ui.py",
    "genie_menu.py",
)

# useful on the bench, not needed to run. Kept, but flagged.
BENCH = (
    "cleanup.py",       # this file. Not needed to RUN, but it used to
                        # mark itself for deletion, which is a confusing
                        # thing for an audit tool to do.
    "doctor_all.py",
    "strip.py",
    "mpu6050.py",
    "hello_tft.py",
    "i2c_doctor.py",
)

# these actively break things if left behind - they shadow the new files
DANGER = (
    "face.py",          # the second eye module. Two of these on one device
                        # is how you debug code that is not running.
    "genie_live.py",
    "onebutton.py",
    "buttons.py",
    "MENU.py",
    "genie_node.py",
    "ui.py",
    "leds.py",
    "levels.py",
    "sensor_hub.py",
    "sensor_menu.py",
)


def _walk(path="/"):
    out = []
    try:
        entries = os.listdir(path)
    except OSError:
        return out
    for name in entries:
        full = path + name if path.endswith("/") else path + "/" + name
        try:
            mode = os.stat(full)[0]
        except OSError:
            continue
        if mode & 0x4000:
            out.append((full, -1))
            out.extend(_walk(full))
        else:
            try:
                out.append((full, os.stat(full)[6]))
            except OSError:
                out.append((full, 0))
    return out


def _classify(full):
    name = full.rsplit("/", 1)[-1]
    if name in KEEP:
        return "KEEP", ""
    if name in DANGER:
        return "DELETE", "shadows the new file - this WILL bite you"
    if name in BENCH:
        return "bench", "not needed to run, harmless"
    if name.endswith(".mpy"):
        return "DELETE", "stale bytecode, shadows the .py"
    if "__pycache__" in full:
        return "DELETE", "pycache"
    if name.startswith("test_"):
        return "bench", "bench test, safe to keep or drop"
    if name.endswith(".py"):
        return "DELETE", "not part of the running system"
    return "other", ""


def audit():
    print("\n" + "=" * 60)
    print("  ESP32 FILE AUDIT   (reads only, deletes nothing)")
    print("=" * 60)
    files = _walk("/")
    if not files:
        print("  could not list the filesystem")
        return []

    buckets = {"KEEP": [], "DELETE": [], "bench": [], "other": []}
    for full, size in files:
        if size == -1:
            continue
        kind, why = _classify(full)
        buckets[kind].append((full, size, why))

    for kind, header in (("KEEP", "REQUIRED - the face will not run without these"),
                         ("bench", "BENCH - keep if you still want them"),
                         ("DELETE", "DELETE - stale, shadowing, or dead"),
                         ("other", "other files")):
        rows = buckets[kind]
        if not rows:
            continue
        print("\n  %s" % header)
        for full, size, why in sorted(rows):
            print("    %-28s %6d  %s" % (full, size, why))

    missing = [k for k in KEEP if not any(
        f.rsplit("/", 1)[-1] == k for f, _ in files)]
    missing = [m for m in missing if m not in ("boot.py", "main.py")]
    if missing:
        print("\n  MISSING - upload these before running genie_ui:")
        for m in missing:
            print("    %s" % m)

    print("\n  %d file(s) marked DELETE. Run cleanup.purge() to remove them."
          % len(buckets["DELETE"]))
    return [f for f, _, _ in buckets["DELETE"]]


def purge(force=False):
    targets = audit()
    if not targets:
        print("\n  nothing to delete")
        return
    print("\n" + "=" * 60)
    for full in targets:
        if not force:
            a = input("  delete %s ?  [y/N] > " % full)
            if a.strip().lower() != "y":
                print("    kept")
                continue
        try:
            os.remove(full)
            print("    removed %s" % full)
        except OSError as e:
            print("    FAILED %s  %r" % (full, e))
    print("\n  done. Hard-reset before running genie_ui:")
    print("      import machine; machine.reset()")


if __name__ == "__main__":
    audit()
