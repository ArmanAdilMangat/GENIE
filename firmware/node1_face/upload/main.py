"""
main.py - autostart, with an escape hatch.

THE RULE: main.py must never retry in a loop.

The old one did. When line 11 threw, it caught the error, printed
"Initialization failed. Bailing out." and went round again - forever, faster
than you can type. That is what filled your console and locked you out of the
REPL. A boot loop on an autostarting board is the single worst failure mode
in MicroPython, because the only way out is a hard erase.

Three rules are baked in below:

    1  A 3 second grace period BEFORE anything is imported. Ctrl-C in that
       window drops you straight to the REPL with nothing running.
    2  ONE attempt. If it throws, it prints the real traceback and STOPS.
       No retry, ever.
    3  The traceback is printed in full, not swallowed into a one-line
       message that tells you nothing.

If you are ever locked out again:
    Ctrl-C repeatedly while pressing reset. If that fails, erase and
    reflash - or hold BOOT while plugging in to reach the bootloader.
"""

import sys
import time

GRACE_S = 3

print()
print("=" * 46)
print("  GENIE starting in %d s" % GRACE_S)
print("  press Ctrl-C NOW for a REPL")
print("=" * 46)

try:
    for i in range(GRACE_S, 0, -1):
        print("  %d ..." % i)
        time.sleep(1)
except KeyboardInterrupt:
    print("\n  cancelled. REPL is yours.\n")
    raise SystemExit

try:
    import genie_ui
    genie_ui.run()
except KeyboardInterrupt:
    print("\n  stopped by Ctrl-C\n")
except Exception as e:
    print("\n" + "!" * 46)
    print("  GENIE failed to start. Full traceback:")
    print("!" * 46)
    sys.print_exception(e)
    print("\n  NOT retrying. Fix it, then:  import machine; machine.reset()\n")
