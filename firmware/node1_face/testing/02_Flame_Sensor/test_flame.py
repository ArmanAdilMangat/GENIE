"""
test_flame.py - IR flame sensor, digital output only.

Wire ONLY this after the TFT passes.
    flame DO -> GPIO42  (P2-6)
    VCC -> 3V3 rail      GND -> common GND

DO is ACTIVE LOW: 0 = flame seen, 1 = no flame.

If the pin reads FLOATING the module is not driving it at all - that is a
power or signal-wire fault, not a sensitivity problem.  Check 3V3 and GND
at the module pins before touching the potentiometer.

    >>> import test_flame
    >>> test_flame.run()
"""

from machine import Pin
import time

FLAME = 42


def wired():
    """Is a module actually driving the pin, or is it hanging in air?"""
    up = Pin(FLAME, Pin.IN, Pin.PULL_UP).value()
    time.sleep_ms(5)
    dn = Pin(FLAME, Pin.IN, Pin.PULL_DOWN).value()
    Pin(FLAME, Pin.IN, None)
    if up == 1 and dn == 0:
        return False, "floating - module not connected or unpowered"
    if up == 1 and dn == 1:
        return True, "driven HIGH - module present, no flame"
    if up == 0 and dn == 0:
        return True, "driven LOW - module present, sees flame (or pot maxed)"
    return False, "unstable"


def check():
    print("=" * 58)
    print("  FLAME SENSOR CHECK  (GPIO%d)" % FLAME)
    print("=" * 58)
    ok, why = wired()
    print("    %s" % why)
    if not ok:
        print("\n  FAIL - fix wiring/power first.")
        return False
    print("\n  PASS - module is on the pin.")
    return True


def live():
    """Live state.  A lighter at ~20 cm should flip it to FLAME instantly.
    If it never flips, turn the pot until the module's second LED just goes
    out with no flame present - that is the correct threshold."""
    p = Pin(FLAME, Pin.IN)
    last = None
    trips = 0
    print("\n  Ctrl-C to stop.\n")
    try:
        while True:
            v = p.value()
            if v != last:
                if v == 0:
                    trips += 1
                    print("  %8d ms   FLAME        (trip %d)"
                          % (time.ticks_ms(), trips))
                else:
                    print("  %8d ms   clear" % time.ticks_ms())
                last = v
            time.sleep_ms(20)
    except KeyboardInterrupt:
        print("\n  stopped.  %d trip(s)." % trips)


def run():
    if check():
        live()


if __name__ == "__main__":
    run()
