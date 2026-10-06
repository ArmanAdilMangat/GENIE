"""Knock / tap input from 4 vibration sensors (SW-420 or similar DO modules).

MUST be saved onto the BOARD if you import it from elsewhere.

DESIGN NOTE — why this is not just pin.value()
    A piezo/spring vibration module does not produce one clean pulse per tap.
    One physical knock produces a burst of 5-40 edges over ~30 ms as the
    element rings down. Naive counting reports a single tap as eight taps.

    So: an interrupt records edge timestamps, a debounce window collapses the
    ring-down burst into ONE tap, and a pattern window groups taps into
    single / double / triple.

TUNING (the three numbers that matter)
    DEBOUNCE_MS   30-60   too low = one knock counts as many
    PATTERN_MS   400-700  gap that ends a pattern; too low splits a double tap
    the pot on the module sets raw sensitivity — do that first, in hardware
"""

from machine import Pin
import time

PINS = [14, 15, 21, 47]
NAMES = ["A", "B", "C", "D"]

DEBOUNCE_MS = 40        # ignore edges this close together — kills ring-down
PATTERN_MS = 500        # silence this long ends the tap pattern
ACTIVE_LOW = True       # most SW-420 boards pull DO low on vibration


class KnockSensor:
    def __init__(self, pin_no, name):
        self.name = name
        self.pin_no = pin_no
        self.taps = 0
        self.last_edge = 0
        self.last_tap = 0
        self._pending = 0

        trigger = Pin.IRQ_FALLING if ACTIVE_LOW else Pin.IRQ_RISING
        pull = Pin.PULL_UP if ACTIVE_LOW else None
        self.pin = Pin(pin_no, Pin.IN, pull)
        self.pin.irq(trigger=trigger, handler=self._isr)

    def _isr(self, pin):
        # Keep this short. No prints, no allocation.
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_edge) < DEBOUNCE_MS:
            return                       # still the same knock ringing down
        self.last_edge = now
        self._pending += 1

    def poll(self):
        """Call from the main loop. Returns tap count when a pattern ends."""
        now = time.ticks_ms()

        if self._pending:
            self.taps += self._pending
            self._pending = 0
            self.last_tap = now
            return None                  # pattern still open

        if self.taps and time.ticks_diff(now, self.last_tap) > PATTERN_MS:
            n = self.taps
            self.taps = 0
            return n                     # pattern complete
        return None

    def deinit(self):
        self.pin.irq(handler=None)


def make_all():
    return [KnockSensor(p, n) for p, n in zip(PINS, NAMES)]


PATTERN_NAMES = {1: "single", 2: "double", 3: "triple"}


def describe(n):
    return PATTERN_NAMES.get(n, "%d taps" % n)


if __name__ == "__main__":
    print("=" * 52)
    print(" KNOCK / TAP TEST")
    print("=" * 52)
    print("pins: %s   active %s" % (PINS, "LOW" if ACTIVE_LOW else "HIGH"))
    print("debounce %d ms, pattern window %d ms\n" % (DEBOUNCE_MS, PATTERN_MS))
    print("Tap each sensor: once, then twice, then three times.")
    print("If a single tap reports as 2+, raise DEBOUNCE_MS.")
    print("If a double tap reports as two singles, raise PATTERN_MS.")
    print("Ctrl+C to stop.\n")

    sensors = make_all()
    try:
        while True:
            for s in sensors:
                n = s.poll()
                if n:
                    print("  [%s] %s" % (s.name, describe(n)))
            time.sleep_ms(10)
    except KeyboardInterrupt:
        for s in sensors:
            s.deinit()
        print("\nstopped")
