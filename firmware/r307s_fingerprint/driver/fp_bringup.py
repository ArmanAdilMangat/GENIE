"""GENIE Node 2 -- R307S bring-up. Run this ONLY after fp_probe.py answers.

SCRIPT. Thonny, F5. Needs r307.py on the board.

fp_probe.py decides whether the module is alive. This file assumes it is and
takes it from handshake to a working enrol/identify, which is the state you
need for the FYP demo.
"""

VERSION = "fp_bringup 1.0  24-08-2026"

import time
from r307 import R307, err, OK

# Set these from what fp_probe.py TEST D reported.
TX, RX, BAUD, TOUCH = 17, 18, 57600, 16

# Values read off this module on 08-08-2026, when it was working. Anything
# different now is a real change, not a fresh baseline to write down.
KNOWN = {"capacity": 1000, "security_level": 3,
         "packet_size": 128, "baud": 57600}


def ask(p):
    try:
        return input(p).strip()
    except (KeyboardInterrupt, EOFError):
        return ""


def rule(c="-"):
    print(c * 62)


def step1_identify_module(fp):
    rule("=")
    print("  STEP 1  who are you?")
    rule("=")
    if not fp.verify_pwd():
        print("  handshake REFUSED. Go back to fp_probe.py.")
        return False
    print("  handshake OK")

    p = fp.read_sysparam()
    if not p:
        print("  could not read parameters")
        return False

    drift = []
    for k, want in KNOWN.items():
        got = p.get(k)
        flag = "" if got == want else "   <-- was %s on 08-08" % want
        if got != want:
            drift.append(k)
        print("  %-15s %s%s" % (k, got, flag))

    n = fp.template_count()
    print("  %-15s %d" % ("templates", n))
    if n > 0:
        used = fp.used_slots()
        if used:
            print("  %-15s %s" % ("slots in use", used))

    if drift:
        print("")
        print("  %d parameter(s) changed since it last worked." % len(drift))
        print("  A module that survived whatever happened would normally")
        print("  report identical values -- these live in its flash.")
    return True


def step2_optics(fp):
    rule("=")
    print("  STEP 2  optics and illumination")
    rule("=")
    print("  Dim the room. Watching the glass.\n")
    fp.ring_sweep()
    print("\n  Now 8 captures. Put a finger down partway through.")
    seen = {}
    for i in range(8):
        c = fp.get_image()
        seen[c] = seen.get(c, 0) + 1
        print("    %d  %s" % (i + 1, err(c)))
        time.sleep(1)
    print("")
    if OK in seen:
        print("  Captured a real image. Optics are good.")
        return True
    if 0x02 in seen and len(seen) == 1:
        print("  Only ever 'no finger'. The module is talking and the")
        print("  protocol is fine, but it never saw skin. Either you did")
        print("  not press, or the prism/LED path is dead. Press firmly,")
        print("  flat, on the CENTRE, and run this step again before")
        print("  blaming the optics.")
    return False


def step3_enrol(fp):
    rule("=")
    print("  STEP 3  enrol")
    rule("=")
    s = ask("  slot number (0-999, blank = 1): ")
    page = int(s) if s else 1
    ok, msg = fp.enroll(page)
    print("  %s" % msg)
    return ok


def step4_identify(fp):
    rule("=")
    print("  STEP 4  identify -- 5 attempts")
    rule("=")
    hits = 0
    for i in range(5):
        print("  attempt %d -- press..." % (i + 1))
        page, score = fp.identify()
        if page >= 0:
            hits += 1
            print("    slot %d  score %d" % (page, score))
        else:
            print("    no match")
        fp.wait_finger(6, want=False)
        time.sleep_ms(400)
    print("")
    print("  %d/5 matched" % hits)
    if hits >= 4:
        print("  Good enough to demo. Put this number in the report.")
    return hits


def main():
    print("\n  %s" % VERSION)
    print("  R307 on tx=%d rx=%d @ %d\n" % (TX, RX, BAUD))
    try:
        fp = R307(tx=TX, rx=RX, baud=BAUD, touch=TOUCH)
    except Exception as e:
        print("  could not open UART: %s" % e)
        return

    if not step1_identify_module(fp):
        return
    ask("\n  [enter] for optics ")
    step2_optics(fp)
    if ask("\n  enrol a finger? (y/n) ").lower().startswith("y"):
        if step3_enrol(fp):
            ask("\n  [enter] to test identify ")
            step4_identify(fp)

    rule("=")
    print("  Done. If all four steps passed, the fingerprint reader is")
    print("  back and Node 2 is unblocked.")
    rule("=")


main()
