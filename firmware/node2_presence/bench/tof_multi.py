"""Multiple VL53L1X on one I2C bus — metres display, scales 2 -> 4 sensors.

Set N_SENSORS to how many are physically wired. Everything else adapts:
bring-up, the live view, and the range characterisation all use only the
first N entries of the tables below. Wire two today, change one number when
the other two arrive.

WIRING  (per sensor)
    VIN   -> 3V3      never 5 V
    GND   -> GND
    SDA   -> GPIO8    shared by every sensor
    SCL   -> GPIO9    shared by every sensor
    XSHUT -> its own GPIO from the XSHUT list below

    Pull-ups: ONE pair of 4.7k, SDA and SCL to 3V3, for the whole bus.
    Several breakout boards each with their own pull-ups makes the bus too
    stiff to drive -- that is a real failure mode with 4 sensors.

WHY XSHUT IS NEEDED
    Every VL53L1X ships at address 0x29. Two or more on one bus all answer at
    once and the bus returns garbage. XSHUT holds a chip in reset while low,
    so we wake them one at a time and give each a private address.

    Those addresses live in sensor RAM, not flash. Every reset and power cycle
    throws them away, so bring_up() must run on every boot. No way around it.

Requires vl53l1x.py and zones.py in the same folder ON THE BOARD.
"""

from machine import I2C, Pin
import time

from vl53l1x import VL53L1X, SHORT, LONG
from zones import ZoneTracker, m, cm

# ------------------------------------------------------------------ config
N_SENSORS = 4                            # all four wired, one per side

SDA, SCL = 8, 9
XSHUT = [10, 11, 12, 13]                 # one GPIO per sensor, in order
ADDRESSES = [0x30, 0x31, 0x32, 0x33]

# Four sides, one sensor each. The ORDER here is the order XSHUT is raised and
# the order addresses are handed out, so index 0 must physically be the front
# sensor on GPIO10 at 0x30. Mixing up which board is which is not a wiring
# fault the code can detect - every sensor is identical - so label the cables
# before mounting them, not after.
NAMES = ["front", "left", "right", "rear"]

MODE = LONG                              # LONG ~4 m. SHORT ~1.3 m but far
                                         # better immunity to ambient light.

BOOT_MS = 15                             # settle after raising XSHUT. Datasheet
                                         # says ~1.2 ms; 2 ms is where flaky
                                         # ENODEV failures come from. Be generous.

MIN_VALID_MM = 40                        # below this the chip saturates
MAX_TRUST_MM = 4000                      # LONG mode ceiling
LOOP_MS = 20
PRINT_MS = 250

# Room-scale zone bands, in mm. Wider than the desk-scale defaults in zones.py
# because this array is meant to watch a room, not a hand.
#
# NOTE the 100 mm TOUCH band with HYST 40: hysteresis must stay below half the
# narrowest band or that band can only be entered via the saturation clamp.
ROOM_ZONES = (
    (100,   "TOUCH"),        # 0 - 10 cm   object against the lens
    (500,   "NEAR"),         # 10 - 50 cm  hand / gesture range
    (1500,  "PRESENT"),      # 0.5 - 1.5 m person at the bed or chair
    (3000,  "FAR"),          # 1.5 - 3 m   in the room, doorway crossing
    (99999, "CLEAR"),        # beyond that nothing meaningful
)
ROOM_HYST_MM = 40
ROOM_STABLE_N = 3


# =================================================================== bring-up
def bring_up(i2c=None, mode=MODE, n=N_SENSORS, verbose=True):
    """Wake sensors one at a time, give each a private address.

    Returns a list of length n. A failed sensor becomes None -- one dead
    sensor must never stop the others from coming up.
    """
    if i2c is None:
        i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL), freq=400000)

    pins = [Pin(p, Pin.OUT, value=0) for p in XSHUT[:n]]   # all asleep
    time.sleep_ms(30)

    if verbose:
        pre = [hex(a) for a in i2c.scan()]
        print("  bus with everything in reset: %s" % pre)
        if "0x29" in pre:
            print("  WARNING: 0x29 answers while all XSHUT are LOW.")
            print("           A sensor's XSHUT is not connected to its GPIO.")
            print("           It will collide during assignment.")

    sensors = []
    for i, pin in enumerate(pins):
        pin.value(1)
        time.sleep_ms(BOOT_MS)
        try:
            s = VL53L1X(i2c, 0x29)
            s.init(mode)
            s.set_address(ADDRESSES[i])
            s.start()
            sensors.append(s)
            if verbose:
                print("  %-6s -> 0x%02X  ok" % (NAMES[i], ADDRESSES[i]))
        except Exception as e:
            sensors.append(None)
            if verbose:
                print("  %-6s -> FAILED: %s" % (NAMES[i], e))
            pin.value(0)                 # park it so it cannot squat on 0x29
            time.sleep_ms(BOOT_MS)

    if verbose:
        live = [hex(a) for a in i2c.scan()]
        print("  bus now: %s" % live)
        alive = sum(1 for s in sensors if s)
        print("  %d of %d sensors live" % (alive, n))
        if alive < n:
            print("\n  Run option 3 (XSHUT diagnostic) -- it says which wire.")
    return sensors


def xshut_diagnostic(n=N_SENSORS):
    """Pull each XSHUT low in turn; 0x29 should vanish. Names the bad wire.

    Run this with NO addresses assigned -- power-cycle the board first, or the
    sensors are already at 0x30+ and will not answer at 0x29.
    """
    print("\n--- XSHUT diagnostic --------------------------------------")
    print("  power-cycle the board before trusting this result\n")
    i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL), freq=100000)

    pins = [Pin(p, Pin.OUT, value=1) for p in XSHUT[:n]]     # all awake
    time.sleep_ms(50)

    found = [hex(a) for a in i2c.scan()]
    print("  all awake, bus: %s" % found)
    if "0x29" not in found:
        print("""
  NOTHING at 0x29 with every sensor awake. Before checking XSHUT:
    - VIN on 3V3 (not 5 V), GND shared with the ESP32
    - 4.7k pull-ups on SDA and SCL to 3V3, ONE pair for the bus
    - SDA on GPIO%d, SCL on GPIO%d
""" % (SDA, SCL))
        return

    for i, p in enumerate(pins):
        p.value(0)
        time.sleep_ms(50)
        gone = 0x29 not in i2c.scan()
        p.value(1)
        time.sleep_ms(50)
        print("  XSHUT #%d %-6s (GPIO%-2d): %s"
              % (i + 1, NAMES[i], XSHUT[i],
                 "controls a sensor" if gone else "NO EFFECT -- check this wire"))

    print("""
  "NO EFFECT" means that GPIO is not reaching that sensor's XSHUT pin, OR
  that sensor is not powered. With several sensors still answering at 0x29,
  pulling one low does not empty the address -- so test with ONE sensor
  connected if the result is ambiguous.""")


# ==================================================================== reading
def read_all(sensors):
    """[mm | 0 | None] per sensor. 0 means saturated (object on the lens)."""
    out = []
    for s in sensors:
        if s is None:
            out.append(None)
            continue
        try:
            if not s.data_ready():       # never block: skip, keep last value
                out.append(-1)
                continue
            mm = s.distance()
            if mm is not None and mm < MIN_VALID_MM:
                mm = 0
            out.append(mm)
        except OSError:
            out.append(None)
    return out


def bar(mm, width=14, full=MAX_TRUST_MM):
    if mm is None:
        return "." * width
    n = int(width * min(mm, full) / full)
    return "#" * n + "-" * (width - n)


def make_trackers(n=N_SENSORS):
    return [ZoneTracker(NAMES[i], ROOM_ZONES, ROOM_HYST_MM, ROOM_STABLE_N)
            for i in range(n)]


# =================================================================== live view
def live(sensors, seconds=0):
    """Distance in metres plus debounced zone. seconds=0 means run forever."""
    n = len(sensors)
    trackers = make_trackers(n)
    last = [None] * n

    print("\n  metres + debounced zone. Ctrl+C to stop.")
    print("  zone changes print on their own line\n")

    dl = time.ticks_add(time.ticks_ms(), int(seconds * 1000)) if seconds else None
    nxt = time.ticks_ms()
    try:
        while dl is None or time.ticks_diff(time.ticks_ms(), dl) < 0:
            r = read_all(sensors)
            for i in range(n):
                if r[i] != -1:                    # -1 = no new sample this pass
                    last[i] = r[i]
                    z = trackers[i].update(r[i])
                    if z:
                        print("      >> %-6s -> %s" % (NAMES[i], z))

            if time.ticks_diff(time.ticks_ms(), nxt) >= 0:
                nxt = time.ticks_add(time.ticks_ms(), PRINT_MS)
                parts = []
                for i in range(n):
                    parts.append("%-6s %s m [%-7s] |%s|"
                                 % (NAMES[i], m(last[i]), trackers[i].zone,
                                    bar(last[i])))
                print("  " + "   ".join(parts))
            time.sleep_ms(LOOP_MS)
    except KeyboardInterrupt:
        print("\n  stopped")


# ========================================================== range characterisation
def characterise(sensors, samples=60):
    """Statistics at a fixed distance. Put a target at a known range first.

    This is how you find the sensor's REAL usable range in your room, which is
    never the datasheet number -- ambient IR, target colour and target size all
    cut it down. Run it at 0.5 m, 1 m, 2 m, 3 m and watch where the invalid
    count climbs and the spread widens.
    """
    n = len(sensors)
    print("\n--- range characterisation --------------------------------")
    print("  place a target at a known distance and hold it still.")
    print("  %d samples per sensor.\n" % samples)
    try:
        input("  press Enter when the target is in place... ")
    except (KeyboardInterrupt, EOFError):
        return

    data = [[] for _ in range(n)]
    invalid = [0] * n
    got = 0
    try:
        while got < samples:
            r = read_all(sensors)
            progressed = False
            for i in range(n):
                if r[i] == -1:
                    continue
                progressed = True
                if r[i] is None:
                    invalid[i] += 1
                else:
                    data[i].append(r[i])
            if progressed:
                got += 1
                if got % 10 == 0:
                    print("    %d/%d" % (got, samples))
            time.sleep_ms(LOOP_MS)
    except KeyboardInterrupt:
        print("  (stopped early)")

    print("\n  sensor    n   mean       min        max        spread   invalid")
    print("  " + "-" * 62)
    for i in range(n):
        d = data[i]
        if not d:
            print("  %-6s    0   no valid readings at all        %d" % (NAMES[i], invalid[i]))
            continue
        mean = sum(d) / len(d)
        lo, hi = min(d), max(d)
        print("  %-6s %4d  %s m  %s m  %s m  %4d mm  %5d"
              % (NAMES[i], len(d), m(int(mean)), m(lo), m(hi), hi - lo, invalid[i]))

    print("""
  READING THIS
    spread   under ~20 mm is a solid reading. Growing spread means you are
             reaching the edge of usable range for this target.
    invalid  a few is normal. Climbing fast means the return signal is too
             weak -- the real limit, well before the datasheet's 4 m.
    mean     compare against the true distance. A constant offset is fine and
             correctable; an offset that grows with distance is not.""")


# ============================================================== single sensor
def single():
    """One sensor at the factory address, no XSHUT. Proves wiring in isolation."""
    print("\n--- single sensor (0x29, XSHUT unused) --------------------")
    i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL), freq=400000)
    found = [hex(a) for a in i2c.scan()]
    print("  bus: %s" % found)
    if "0x29" not in found:
        print("  nothing at 0x29. XSHUT held low? pull-ups? VIN on 3V3?")
        return
    s = VL53L1X(i2c, 0x29)
    s.init(MODE)
    s.start()
    print("  OK  model ID 0x%04X" % s.model_id())
    live([s])
    s.stop()


# ======================================================================= menu
MENU = """
============================================================
 VL53L1X ARRAY  --  %d sensor(s) configured
============================================================
  1  bring up + live view      (metres, zones, all sensors)
  2  range characterisation    (statistics at a fixed distance)
  3  XSHUT diagnostic          (which wire is wrong)
  4  single sensor only        (0x29, no XSHUT)
  5  set mode  LONG <-> SHORT   (currently %s)
  0  quit
------------------------------------------------------------"""


def _ask(p):
    try:
        return input(p).strip()
    except (KeyboardInterrupt, EOFError):
        return None


def main():
    global MODE
    sensors = None
    while True:
        print(MENU % (N_SENSORS, "LONG" if MODE == LONG else "SHORT"))
        c = _ask("  select: ")
        if c is None or c == "0":
            if sensors:
                for s in sensors:
                    if s:
                        try:
                            s.stop()
                        except Exception:
                            pass
            print("bye")
            return

        if c == "1":
            print("\n--- bring-up ----------------------------------------------")
            sensors = bring_up(mode=MODE)
            if any(sensors):
                live(sensors)
        elif c == "2":
            if not sensors or not any(sensors):
                print("\n  bring the sensors up first (option 1)")
            else:
                characterise(sensors)
        elif c == "3":
            xshut_diagnostic()
        elif c == "4":
            single()
        elif c == "5":
            MODE = SHORT if MODE == LONG else LONG
            print("  mode is now %s -- re-run option 1 to apply"
                  % ("LONG" if MODE == LONG else "SHORT"))
        else:
            print("  '%s'? pick 0-5." % c)


if __name__ == "__main__":
    main()
