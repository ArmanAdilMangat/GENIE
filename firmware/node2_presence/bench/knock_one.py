"""ONE SW-420 vibration module — calibrate first, then count taps.

WHY NOT JUST RUN knock.py
    knock.py assumes four modules and a known output polarity. Both of those
    are guesses right now. The two things that actually break an SW-420 bring-up
    are the potentiometer being mis-set and the DO polarity being inverted on
    clone boards. So this script does those first, in that order, and only
    then turns on tap logic.

WIRING
    VCC -> 3V3
    GND -> GND
    DO  -> GPIO14
    AO  -> leave unconnected (4-pin boards only; we do not use the analog out)

Standalone. Nothing to upload — just F5.
"""

from machine import Pin
import time

PIN = 14

DEBOUNCE_MS = 40        # ignore edges this close together -- kills ring-down
PATTERN_MS = 500        # silence this long ends the tap pattern
CALIBRATE_MS = 3000     # how long to watch the idle line at startup


def calibrate(pin_no, ms=CALIBRATE_MS):
    """Watch the resting line. Returns (active_low, idle_level, flips)."""
    p = Pin(pin_no, Pin.IN)
    t0 = time.ticks_ms()
    hi = lo = 0
    flips = 0
    last = p.value()
    while time.ticks_diff(time.ticks_ms(), t0) < ms:
        v = p.value()
        if v:
            hi += 1
        else:
            lo += 1
        if v != last:
            flips += 1
            last = v
        time.sleep_ms(1)

    idle = 1 if hi > lo else 0
    return (idle == 1), idle, flips


class Knock:
    def __init__(self, pin_no, active_low):
        self.taps = 0
        self.last_edge = 0
        self.last_tap = 0
        self._pending = 0
        pull = Pin.PULL_UP if active_low else None
        trig = Pin.IRQ_FALLING if active_low else Pin.IRQ_RISING
        self.pin = Pin(pin_no, Pin.IN, pull)
        self.pin.irq(trigger=trig, handler=self._isr)

    def _isr(self, pin):
        now = time.ticks_ms()                     # keep short: no print, no alloc
        if time.ticks_diff(now, self.last_edge) < DEBOUNCE_MS:
            return
        self.last_edge = now
        self._pending += 1

    def poll(self):
        now = time.ticks_ms()
        if self._pending:
            self.taps += self._pending
            self._pending = 0
            self.last_tap = now
            return None
        if self.taps and time.ticks_diff(now, self.last_tap) > PATTERN_MS:
            n, self.taps = self.taps, 0
            return n
        return None

    def deinit(self):
        self.pin.irq(handler=None)


NAMES = {1: "single", 2: "double", 3: "triple"}


def main():
    print("=" * 52)
    print(" SW-420 KNOCK TEST  (DO on GPIO%d)" % PIN)
    print("=" * 52)
    print("\nCALIBRATING -- do not touch the sensor for %d seconds." % (CALIBRATE_MS // 1000))

    active_low, idle, flips = calibrate(PIN)
    print("  idle level : %s" % ("HIGH" if idle else "LOW"))
    print("  edges while idle: %d" % flips)

    if flips > 40:
        print("""
  POT IS TOO SENSITIVE. The output is chattering with nothing touching it.
  Turn the potentiometer down until this count is near zero, then re-run.
  Do this in hardware first -- no amount of debouncing fixes a hot pot.""")
        return

    print("  polarity   : active %s (auto-detected)" % ("LOW" if active_low else "HIGH"))
    print("\nTap once, then twice, then three times.")
    print("  single tap reported as 2+   -> raise DEBOUNCE_MS")
    print("  double tap read as 2 singles -> raise PATTERN_MS")
    print("Ctrl+C to stop.\n")

    k = Knock(PIN, active_low)
    try:
        while True:
            n = k.poll()
            if n:
                print("  %s  (%d)" % (NAMES.get(n, "%d taps" % n), n))
            time.sleep_ms(10)
    except KeyboardInterrupt:
        k.deinit()
        print("\nstopped")


if __name__ == "__main__":
    main()
