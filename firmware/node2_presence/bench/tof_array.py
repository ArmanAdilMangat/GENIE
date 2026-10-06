"""Four VL53L1X on one I2C bus — address assignment and read loop.

THE WHOLE POINT OF THIS FILE
    Every VL53L1X ships at address 0x29. Four on one bus all answer at once
    and the bus returns garbage. The fix is XSHUT: hold all four in reset,
    then wake them one at a time and give each a private address.

    The new addresses live in RAM, not flash. Every reset and every power
    cycle throws them away. bring_up() therefore has to run at the top of
    main.py on EVERY boot. There is no way around this.

Requires vl53l1x.py on the board.
"""

from machine import I2C, Pin
import time
from vl53l1x import VL53L1X, SHORT, LONG

SDA, SCL = 8, 9
XSHUT = [10, 11, 12, 13]
ADDRESSES = [0x30, 0x31, 0x32, 0x33]
NAMES = ["front", "left", "right", "rear"]      # rename to match your mounting
MODE = LONG


def bring_up(i2c=None, mode=MODE, verbose=True):
    """Returns a list of live VL53L1X objects. Missing sensors become None."""
    if i2c is None:
        i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL), freq=400000)

    pins = [Pin(p, Pin.OUT, value=0) for p in XSHUT]   # all asleep
    time.sleep_ms(20)

    sensors = []
    for i, pin in enumerate(pins):
        pin.value(1)                 # wake this one only
        time.sleep_ms(5)             # boot time; 2 ms is the datasheet minimum

        try:
            s = VL53L1X(i2c, 0x29)
            s.init(mode)
            s.set_address(ADDRESSES[i])
            s.start()
            sensors.append(s)
            if verbose:
                print("  %-6s -> 0x%02X  ok" % (NAMES[i], ADDRESSES[i]))
        except OSError as e:
            sensors.append(None)
            if verbose:
                print("  %-6s -> FAILED: %s" % (NAMES[i], e))
            pin.value(0)             # park it so it can't squat on 0x29
            time.sleep_ms(5)

    if verbose:
        live = [hex(a) for a in i2c.scan()]
        print("  bus now: %s" % live)
        if "0x29" in live:
            print("  WARNING: 0x29 still present -- one sensor was not")
            print("  reassigned and will collide with the next bring_up().")
    return sensors


MIN_VALID_MM = 40       # below this the sensor saturates and reports garbage
MAX_TRUST_MM = 1500     # beyond this, indoors with ambient light, don't trust it
NEAR = -1               # marker: something is there, too close to measure

DISPLAY_UNIT = "cm"     # display only. All logic below stays in integer mm.

# Zone classification lives in zones.py -- ONE source of truth.
# The duplicate ZONES/zone()/to_cm()/fmt() that used to be here disagreed with
# zones.py on what "TOUCH" and "FAR" meant. Deleted rather than reconciled.


def read_all(sensors):
    """[mm | NEAR | None] * 4, same order as NAMES.

    NEAR (-1) means an object is present but closer than the sensor can
    resolve. The chip reports status 'valid' with a distance of 0-30 mm when
    saturated, which is why a raw distance() alone is not enough -- 0 mm and
    'nothing there' look identical otherwise.
    """
    out = []
    for s in sensors:
        if s is None:
            out.append(None)
            continue
        try:
            mm = s.distance()
            if mm is None:
                out.append(None)
            elif mm < MIN_VALID_MM:
                out.append(NEAR)
            else:
                out.append(mm)
        except OSError:
            out.append(None)
    return out


if __name__ == "__main__":
    from zones import ZoneTracker, cm

    print("=" * 56)
    print(" VL53L1X x4 BRING-UP")
    print("=" * 56)
    print("assigning addresses...")
    sensors = bring_up()

    n = sum(1 for s in sensors if s)
    print("\n%d of 4 sensors live\n" % n)
    if n == 0:
        print("Run i2c_scan.py -- nothing came up.")
        raise SystemExit

    trackers = [ZoneTracker(nm) for nm in NAMES]

    print("distance in cm + debounced zone. Ctrl+C to stop.")
    print("zone changes are printed on their own line\n")
    try:
        while True:
            readings = read_all(sensors)
            # NEAR marker back to a real mm value for the zone logic
            mms = [None if r is None else (0 if r == NEAR else r)
                   for r in readings]

            line = "  ".join("%s %s" % (nm, cm(mm))
                             for nm, mm in zip(NAMES, mms))
            zline = "  ".join("%-7s" % t.zone for t in trackers)
            print("%s   |  %s" % (line, zline))

            for t, mm in zip(trackers, mms):
                changed = t.update(mm)
                if changed:
                    print("      >> %s -> %s" % (t.name, changed))

            time.sleep_ms(150)
    except KeyboardInterrupt:
        for s in sensors:
            if s:
                s.stop()
        print("\nstopped")
