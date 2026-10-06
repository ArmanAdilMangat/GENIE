"""ONE VL53L1X — the minimum viable test. No XSHUT, no address juggling.

WHY THIS FILE EXISTS
    tof_array.py has to solve a problem that does not exist with one sensor:
    four boards all answering at 0x29. With a single sensor there is no
    collision, so XSHUT can be left floating (or tied to 3V3) and the sensor
    just sits at its factory address. Nothing to assign, nothing to lose on
    reset.

    Get this working before going back to four. If this fails, the problem is
    wiring, power or the driver — not the bring-up sequence.

WIRING
    VIN -> 3V3      (NOT 5V — these are 2.8V parts behind an LDO)
    GND -> GND
    SDA -> GPIO8
    SCL -> GPIO9
    XSHUT -> leave unconnected, or to 3V3
    Pull-ups: 4.7k on SDA and SCL to 3V3. One pair total. Many breakout
    boards already have them — check before adding more.

Requires vl53l1x.py and zones.py on the board.
"""

from machine import I2C, Pin
import time

from vl53l1x import VL53L1X, SHORT, LONG
from zones import ZoneTracker, cm

SDA, SCL = 8, 9
MODE = LONG             # LONG ~4 m. Use SHORT for better ambient-light immunity.
MIN_VALID_MM = 40       # below this the sensor saturates and reports garbage
PERIOD_MS = 120


def main():
    i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL), freq=400000)

    found = [hex(a) for a in i2c.scan()]
    print("bus: %s" % found)
    if "0x29" not in found:
        print("\nNo sensor at 0x29.")
        print("  - XSHUT held low? It must float or be high.")
        print("  - VIN on 3V3, GND shared, pull-ups present?")
        print("  - Run i2c_scan.py for the full diagnosis.")
        return

    s = VL53L1X(i2c, 0x29)
    s.init(MODE)
    print("model ID 0x%04X, mode %s" % (s.model_id(), "LONG" if MODE == LONG else "SHORT"))
    s.start()

    tracker = ZoneTracker("tof")
    print("\ncm + debounced zone. Ctrl+C to stop.")
    print("zone changes print on their own line\n")

    try:
        while True:
            try:
                mm = s.distance()
            except OSError as e:
                print("  read error: %s" % e)
                time.sleep_ms(200)
                continue

            # Saturation: the chip reports 'valid' at 0-30 mm when an object is
            # against the lens. Clamp to 0 so it lands in TOUCH, not a fake
            # short distance. None stays None — that means 'no target'.
            if mm is not None and mm < MIN_VALID_MM:
                mm = 0

            changed = tracker.update(mm)
            print("  %s cm   [%-7s]" % (cm(mm), tracker.zone))
            if changed:
                print("      >> %s" % changed)

            time.sleep_ms(PERIOD_MS)
    except KeyboardInterrupt:
        s.stop()
        print("\nstopped")


if __name__ == "__main__":
    main()
