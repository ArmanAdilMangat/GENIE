"""
test_sw420.py - SW-420 vibration / knock, both modules.

Wire ONLY these after the TFT passes.
    SW-420 top DO    -> GPIO41  (P2-7)
    SW-420 bottom DO -> GPIO40  (P2-8)
    VCC -> 3V3 rail    GND -> common GND

The SW-420 is a rolling-ball switch, not an accelerometer.  It chatters:
one tap produces a burst of edges, not one edge.  Anything that counts raw
edges will over-count by 5-20x.  This file debounces in the ISR with a
fixed window, which is the only thing that makes the count mean anything.

DO idles HIGH and pulses LOW on movement on most boards, but a few are
inverted.  check() works out which yours is instead of assuming.

    >>> import test_sw420
    >>> test_sw420.run()
"""

from machine import Pin
import time

TOP = 41
BOT = 40
DEBOUNCE_MS = 120               # one knock = one count, tuned on the bench


def wired(pin):
    up = Pin(pin, Pin.IN, Pin.PULL_UP).value()
    time.sleep_ms(5)
    dn = Pin(pin, Pin.IN, Pin.PULL_DOWN).value()
    Pin(pin, Pin.IN, None)
    if up == 1 and dn == 0:
        return False, "floating - module not connected or unpowered"
    return True, ("driven HIGH (idle)" if up else "driven LOW (idle inverted)")


def check():
    print("=" * 58)
    print("  SW-420 CHECK")
    print("=" * 58)
    ok = True
    for name, pin in (("top   ", TOP), ("bottom", BOT)):
        good, why = wired(pin)
        print("    %s  GPIO%-2d  %s" % (name, pin, why))
        ok = ok and good
    if not ok:
        print("\n  FAIL - a floating line is power or wiring, never the pot.")
        return False
    print("\n  PASS - both modules are driving their pins.")
    return True


class Knock:
    def __init__(self, pin, name):
        self.name = name
        self.count = 0
        self.last = 0
        self.pin = Pin(pin, Pin.IN)
        self.pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING,
                     handler=self._isr)

    def _isr(self, _):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last) < DEBOUNCE_MS:
            return                       # same knock still ringing
        self.last = now
        self.count += 1

    def stop(self):
        self.pin.irq(handler=None)


def live(seconds=60):
    """Tap the board near each module.  One firm tap should add exactly 1.
    If it adds 3-4, raise DEBOUNCE_MS.  If two taps add 1, lower it."""
    a = Knock(TOP, "top")
    b = Knock(BOT, "bottom")
    print("\n  Tap near each sensor.  %d s, or Ctrl-C.\n" % seconds)
    pa = pb = -1
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            if a.count != pa or b.count != pb:
                print("  top %3d      bottom %3d" % (a.count, b.count))
                pa, pb = a.count, b.count
            time.sleep_ms(50)
    except KeyboardInterrupt:
        pass
    a.stop()
    b.stop()
    print("\n  final:  top %d   bottom %d" % (a.count, b.count))
    if a.count == 0 or b.count == 0:
        print("  A zero means that module never fired.  Turn its pot")
        print("  counter-clockwise to make it more sensitive, then re-run.")
    return a.count, b.count


def run():
    if check():
        live()


if __name__ == "__main__":
    run()
