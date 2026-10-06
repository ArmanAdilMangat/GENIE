"""GENIE Node 2 -- EVERY ToF test, in one file.

SCRIPT. Open in Thonny, press F5. Do not upload it.

ONLY ONE THING MUST BE ON THE BOARD:  vl53l1x.py
Nothing else. No pins3, no tof3, no zones. All of that is inlined below so a
half-finished upload cannot break this file.

If F5 ever gives MemoryError, upload this file too and run:
    import TOF_ALL_TESTS as T; T.main()

WIRING
    every sensor:  VIN->3V3   GND->GND   SDA->GPIO8   SCL->GPIO9
    per sensor:    XSHUT -> its own GPIO (10 / 11 / 12 / 13)
    addresses assigned at bring-up: 0x30 0x31 0x32 0x33

    NOTHING in front of the lens. Not tape, not clear plastic. Cover glass
    causes optical crosstalk and the sensor reads a fixed short distance
    forever.
"""

VERSION = "TOF_ALL_TESTS 1.0  2026-08-15"

from machine import I2C, Pin
import time
import json

# =============================================================== CONFIG
# Edit here and nowhere else.

# How many are PHYSICALLY wired right now. This is the ONLY number to change
# as you add sensors: 2 -> 3 -> 4. It always uses the FIRST N entries of the
# tables below, so with N_SENSORS = 2 your two sensors must be on GPIO10 and
# GPIO11 -- not any other pair.
N_SENSORS = 5
SDA, SCL  = 8, 9
I2C_FREQ  = 400_000                 # drop to 100_000 if the bus is flaky

XSHUT     = [10, 11, 12, 13]        # one GPIO per sensor, in order
ADDRESSES = [0x30, 0x31, 0x32, 0x33]
NAMES     = ["front", "left", "right", "rear"]

BOOT_MS      = 15                   # settle after raising XSHUT
SATURATE_MM  = 40                   # below this the chip saturates and lies
MAX_TRUST_MM = 4000                 # LONG mode ceiling

# thresholds derived at calibration
MARGIN_MM            = 150
MIN_THRESHOLD_MM     = 100
MAX_THRESHOLD_MM     = 1200
DEFAULT_THRESHOLD_MM = 800
HYST_MM              = 60
CONFIRM_N            = 2

# status LED: v1.1 DevKitC = GPIO38, v1.0 = GPIO48. Test 1 finds out.
RGB_PIN     = 38
RGB_ALT_PIN = 48
RGB_COUNT   = 1
BRIGHTNESS  = 40

COL_CLEAR  = (0, 1, 0)
COL_DETECT = (1, 0, 0)
COL_CAL    = (0, 0, 1)
COL_FAULT  = (1, 0, 1)

LOOP_MS  = 20
PRINT_MS = 300

CAL_FILE = "/tof_cal.json"
CSV_FILE = "/tof_results.csv"

MODEL_ID_L1X = 0xEACC
MODEL_ID_L0X = 0x00EE

# ================================================================ STATE
S = {"i2c": None, "sensors": [], "cal": None, "sweeps": {}, "np": None}


# ============================================================== helpers
def ask(prompt):
    try:
        return input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        return None


def pause():
    ask("\n  [enter] to continue ")


def cm(mm, width=6):
    """mm -> right-padded cm string. MicroPython has no str.rjust."""
    if mm is None:
        s = "----"
    else:
        s = "%.1f" % (mm / 10.0)
    return " " * (width - len(s)) + s if len(s) < width else s


def bar(mm, width=14, full=1500):
    if mm is None:
        return "." * width
    n = int(width * min(mm, full) / full)
    return "#" * n + "-" * (width - n)


def stats(vals):
    if not vals:
        return None
    n = len(vals)
    mean = sum(vals) / n
    var = sum((x - mean) ** 2 for x in vals) / n
    return {"n": n, "min": min(vals), "max": max(vals),
            "mean": mean, "sd": var ** 0.5}


def verdict(st):
    if st is None:
        return "no samples -- sensor silent"
    mean, sd = st["mean"], st["sd"]
    if mean < 100:
        d = "BLOCKED -- something against the lens"
    elif mean < 500:
        d = "close surface at %d cm" % (mean / 10)
    elif mean < 1500:
        d = "surface at %.1f m" % (mean / 1000)
    elif mean < MAX_TRUST_MM:
        d = "far surface at %.1f m" % (mean / 1000)
    else:
        d = "open space -- nothing in range"
    if sd > 50:
        d += "  (NOISY sd %d mm)" % sd
    return d


def pulled_up(pin_no):
    """Is there a REAL external pull-up on this line?

    A plain Pin.IN read cannot tell 'externally pulled high' from 'floating,
    still holding the charge we just put on it'. That ambiguity will send you
    chasing a lockup that is really a disconnected wire -- it did exactly that
    on 15-08-2026.

    An internal pull-down is ~45k. A breakout's pull-up is ~10k and wins
    easily. So: enable the pull-down and see who is stronger.
        reads 1 -> a real external pull-up is fighting it. Wire is connected.
        reads 0 -> nothing out there. Floating.
    """
    p = Pin(pin_no, Pin.IN, Pin.PULL_DOWN)
    time.sleep_ms(2)
    v = p.value()
    Pin(pin_no, Pin.IN)                  # release the pull-down
    return v == 1


def bus_health(verbose=True):
    """Idle levels plus a real pull-up test. Far more informative than scan(),
    which returns [] identically for 'not wired', 'not powered' and 'jammed'."""
    s_lvl, c_lvl = Pin(SDA, Pin.IN).value(), Pin(SCL, Pin.IN).value()
    s_pu, c_pu = pulled_up(SDA), pulled_up(SCL)
    if verbose:
        print("  SDA: level=%d  external pull-up=%s" % (s_lvl, "YES" if s_pu else "NO"))
        print("  SCL: level=%d  external pull-up=%s" % (c_lvl, "YES" if c_pu else "NO"))
        if s_pu and c_pu:
            print("  bus wiring is REAL -- sensors powered and connected")
            if not s_lvl:
                print("  ...but SDA is being held LOW: lockup, recoverable")
        elif not s_pu and not c_pu:
            print("  NEITHER line has a pull-up.")
            print("    -> sensors unpowered, or SDA and SCL both disconnected.")
            print("       Check VIN/GND at the sensor first.")
        elif not s_pu:
            print("  SDA has NO external pull-up but SCL does.")
            print("    -> the sensor IS powered (SCL proves it), but the SDA")
            print("       wire is not reaching it. Replace that jumper --")
            print("       do not just re-seat it, dupont wires break inside.")
        else:
            print("  SCL has NO external pull-up but SDA does.")
            print("    -> the SCL wire is not reaching the sensor.")
    return s_pu and c_pu and s_lvl and c_lvl


def bus_recover(verbose=True):
    """Free a bus where a slave is holding SDA low.

    Only meaningful when the wiring is real. If SDA has no external pull-up
    there is nothing to recover -- clocking a disconnected wire achieves
    nothing and reporting success would be a lie.
    """
    if not pulled_up(SDA):
        if verbose:
            print("  SDA has no external pull-up -- nothing to recover.")
            print("  That wire is not connected to a powered sensor.")
        return False
    if Pin(SDA, Pin.IN).value():
        return True                      # already free
    if verbose:
        print("  SDA held low by a slave -- clocking the bus free...")
    scl = Pin(SCL, Pin.OUT, value=1)
    for _ in range(9):
        scl.value(0)
        time.sleep_us(5)
        scl.value(1)
        time.sleep_us(5)
    sda_o = Pin(SDA, Pin.OUT, value=0)   # STOP: SDA low->high while SCL high
    time.sleep_us(5)
    sda_o.value(1)
    time.sleep_us(5)
    Pin(SDA, Pin.IN)
    time.sleep_ms(2)                     # let any residual charge decay
    ok = Pin(SDA, Pin.IN).value() == 1
    if verbose:
        print("  bus %s" % ("recovered" if ok else "STILL HELD LOW"))
        if not ok:
            print("    SDA is shorted to GND. Continuity GPIO%d to GND" % SDA)
            print("    should read OPEN.")
    return ok


def make_i2c(freq=None):
    bus_recover(verbose=False)
    return I2C(0, sda=Pin(SDA), scl=Pin(SCL), freq=freq or I2C_FREQ)


def all_low(n=None):
    n = n if n else N_SENSORS
    pins = [Pin(p, Pin.OUT, value=0) for p in XSHUT[:n]]
    time.sleep_ms(30)
    return pins


# --------------------------------------------------------------- zones
ZONES = ((100, "TOUCH"), (500, "NEAR"), (1500, "PRESENT"),
         (3000, "FAR"), (99999, "CLEAR"))
ZONE_HYST = 40
ZONE_STABLE = 3


def zone_of(mm):
    if mm is None:
        return "CLEAR"
    for limit, name in ZONES:
        if mm < limit:
            return name
    return "CLEAR"


class ZoneTrack:
    """Hysteresis gates on the zone you are LEAVING, not the one you enter.
    The naive form creates a dead band below every boundary that can never be
    entered -- someone standing still at 29 cm reads CLEAR forever."""

    def __init__(self, name):
        self.name = name
        self.zone = "CLEAR"
        self._cand = "CLEAR"
        self._n = 0

    def _ok(self, mm, new):
        for limit, nm in ZONES:
            if nm == self.zone:
                cur = limit
                break
        else:
            return True
        if new == self.zone:
            return True
        return mm > cur + ZONE_HYST or mm < cur - ZONE_HYST

    def update(self, mm):
        if mm is None:
            return None
        z = zone_of(mm)
        if z == self._cand:
            self._n += 1
        else:
            self._cand, self._n = z, 1
        if (z != self.zone and self._n >= ZONE_STABLE and self._ok(mm, z)):
            self.zone = z
            return z
        return None


# ================================================================= LED
def led(pin=None, count=None):
    if S["np"] is not None:
        return S["np"]
    try:
        from neopixel import NeoPixel
        S["np"] = NeoPixel(Pin(pin or RGB_PIN, Pin.OUT), count or RGB_COUNT)
        led_off()
    except Exception as e:
        print("  (no status LED on GPIO%d: %s)" % (pin or RGB_PIN, e))
        S["np"] = False
    return S["np"]


def led_all(rgb):
    np = led()
    if not np:
        return
    v = tuple(int(c * BRIGHTNESS) for c in rgb)
    for i in range(np.n if hasattr(np, "n") else RGB_COUNT):
        np[i] = v
    np.write()


def led_off():
    np = S["np"]
    if not np:
        return
    for i in range(np.n if hasattr(np, "n") else RGB_COUNT):
        np[i] = (0, 0, 0)
    np.write()


# ===================================================================
# TEST 1 -- find the LED pin
# ===================================================================
def t1_find_led():
    print("\n=== TEST 1: find the status LED pin ========================")
    print("  Watch the small RGB LED on the DevKitC.")
    try:
        from neopixel import NeoPixel
    except ImportError:
        print("  neopixel module missing from this firmware. Skip the LED.")
        return
    for pin in (RGB_PIN, RGB_ALT_PIN):
        print("\n  --- GPIO%d ---" % pin)
        try:
            np = NeoPixel(Pin(pin, Pin.OUT), 1)
            for nm, col in (("RED", (1, 0, 0)), ("GREEN", (0, 1, 0)),
                            ("BLUE", (0, 0, 1))):
                np[0] = tuple(int(c * BRIGHTNESS) for c in col)
                np.write()
                print("     %s" % nm)
                time.sleep(1)
            np[0] = (0, 0, 0)
            np.write()
        except Exception as e:
            print("     failed: %s" % e)
    print("\n  Whichever pin lit up -> set RGB_PIN at the top of this file.")
    print("  DevKitC-1 v1.1 uses GPIO38, v1.0 uses GPIO48.")


# ===================================================================
# TEST 2 -- raw I2C scan
# ===================================================================
def t2_scan():
    print("\n=== TEST 2: raw I2C scan ===================================")
    bus_health()
    bus_recover()
    i2c = make_i2c()
    found = i2c.scan()
    print("  bus: %s" % [hex(a) for a in found])
    if not found:
        print("\n  EMPTY BUS. In this order:")
        print("    1. VIN on 3V3 for every sensor (NOT 5V)")
        print("    2. GND common")
        print("    3. SDA on GPIO%d, SCL on GPIO%d" % (SDA, SCL))
        print("    4. all XSHUT currently low? that silences everything --")
        print("       run test 3 or 5, they drive XSHUT deliberately")
    elif 0x29 in found and len(found) == 1:
        print("\n  Only 0x29 -- normal BEFORE bring-up. Run test 5.")
    elif 0x29 in found:
        print("\n  0x29 present ALONGSIDE assigned addresses.")
        print("  A sensor reset, or one XSHUT is not wired. Run test 3.")
    else:
        print("\n  All sensors already have private addresses.")
    return found


# ===================================================================
# TEST 3 -- XSHUT wiring diagnostic  (names the bad wire)
# ===================================================================
def t3_xshut():
    print("\n=== TEST 3: XSHUT wiring diagnostic ========================")
    print("  POWER-CYCLE THE BOARD before trusting this. If bring-up already")
    print("  ran, sensors sit at 0x30+ and will not answer at 0x29.\n")

    i2c = make_i2c(100_000)
    pins = [Pin(p, Pin.OUT, value=1) for p in XSHUT[:N_SENSORS]]   # all awake
    time.sleep_ms(50)
    awake = i2c.scan()
    print("  all XSHUT HIGH : %s" % [hex(a) for a in awake])

    for p in pins:
        p.value(0)
    time.sleep_ms(BOOT_MS * 2)
    asleep = i2c.scan()
    print("  all XSHUT LOW  : %s" % [hex(a) for a in asleep])

    if 0x29 in asleep:
        print("\n  !! 0x29 answers while every XSHUT is LOW.")
        print("     At least one sensor's XSHUT is NOT connected to its GPIO.")
        print("     That sensor is permanently awake and will collide.")
    elif not awake:
        print("\n  !! nothing answers even with every XSHUT HIGH.")
        print("     No sensor is powered, or SDA/SCL are not connected.")
        print("     Check VIN and GND before chasing XSHUT.")
        return
    else:
        print("\n  good: all XSHUT lines can silence their sensor.")

    print("\n  --- wake each one alone (the definitive test) ---")
    bad = []
    for i in range(N_SENSORS):
        for p in pins:
            p.value(0)
        time.sleep_ms(BOOT_MS)
        pins[i].value(1)
        time.sleep_ms(BOOT_MS)
        seen = i2c.scan()
        ok = 0x29 in seen
        if not ok:
            bad.append(i)
        print("    %-6s XSHUT GPIO%-3d -> %-6s   bus %s"
              % (NAMES[i], XSHUT[i], "OK" if ok else "SILENT",
                 [hex(a) for a in seen]))

    for p in pins:
        p.value(1)

    if not bad:
        print("\n  All %d sensors wake individually. Wiring is good." % N_SENSORS)
        return

    print("\n  SILENT: %s" % ", ".join(NAMES[i] for i in bad))
    print("\n  A sensor that never appears -- even with its own XSHUT HIGH")
    print("  and every other one LOW -- is almost never an XSHUT problem.")
    print("  In order of likelihood:")
    print("    1. VIN or GND not connected on that board")
    print("    2. SDA or SCL not landing on that board specifically")
    print("    3. the board itself is dead")
    print("\n  Run test 4 on it -- it walks you through proving which.")


# ===================================================================
# TEST 4 -- deep diagnosis of ONE sensor
# ===================================================================
def t4_one_sensor():
    print("\n=== TEST 4: deep diagnosis, one sensor =====================")
    for i in range(N_SENSORS):
        print("   %d  %s   (XSHUT GPIO%d)" % (i + 1, NAMES[i], XSHUT[i]))
    c = ask("  which sensor is misbehaving? ")
    if c is None:
        return
    try:
        idx = int(c) - 1
    except ValueError:
        print("  '%s'?" % c)
        return
    if idx < 0 or idx >= N_SENSORS:
        return

    name, xp = NAMES[idx], XSHUT[idx]
    i2c = make_i2c(100_000)
    print("\n  diagnosing %s on XSHUT GPIO%d\n" % (name.upper(), xp))

    # step A: everyone else asleep, this one awake
    others = [Pin(XSHUT[j], Pin.OUT, value=0)
              for j in range(N_SENSORS) if j != idx]
    me = Pin(xp, Pin.OUT, value=1)
    time.sleep_ms(BOOT_MS * 2)
    a = i2c.scan()
    print("  A) only %s awake      : %s" % (name, [hex(x) for x in a]))

    # step B: this one asleep too
    me.value(0)
    time.sleep_ms(BOOT_MS * 2)
    b = i2c.scan()
    print("  B) everything asleep  : %s" % [hex(x) for x in b])

    # step C: XSHUT released to input -- board pull-up should wake it
    Pin(xp, Pin.IN)
    time.sleep_ms(BOOT_MS * 4)
    c2 = i2c.scan()
    print("  C) %s XSHUT floating : %s" % (name, [hex(x) for x in c2]))

    print("\n  --- what this means -------------------------------------")
    if 0x29 in a:
        print("  Sensor responds when woken. It is FINE.")
        print("  If bring-up still fails, the address write is the problem --")
        print("  try I2C_FREQ = 100_000 at the top of this file.")
    elif 0x29 in c2:
        print("  Sensor is ALIVE but only appears with XSHUT floating.")
        print("  -> the XSHUT wire from GPIO%d is not reaching the board," % xp)
        print("     or it is on the wrong pin at the sensor end.")
    else:
        print("  Sensor NEVER appears, under any XSHUT state.")
        print("  It is not an XSHUT fault. Do this, in order:")
        print("    1. DMM: is there 3.3 V between that board's VIN and GND?")
        print("       If not -- that is your whole problem.")
        print("    2. Continuity: that board's SDA to GPIO%d, SCL to GPIO%d."
              % (SDA, SCL))
        print("       A dupont that looks seated is often not.")
        print("    3. SWAP TEST -- the one that settles it:")
        print("       physically swap this board with a WORKING one.")
        print("         fault moves with the board  -> the board is dead")
        print("         fault stays on GPIO%d       -> the wiring is bad" % xp)
    print("\n  (leaving all XSHUT high)")
    for p in others:
        p.value(1)
    Pin(xp, Pin.OUT, value=1)


# ===================================================================
# TEST 5 -- bring up the array
# ===================================================================
def _w(i2c, addr, reg, val):
    i2c.writeto(addr, bytes([reg >> 8, reg & 0xFF, val]))


def t5_bring_up(mode=None, verbose=True):
    from vl53l1x import VL53L1X, LONG
    if mode is None:
        mode = LONG
    print("\n=== TEST 5: bring up the array =============================")
    if not (pulled_up(SDA) and pulled_up(SCL)):
        bus_health()
        print("\n  Not attempting bring-up. Every sensor would report")
        print("  'did not wake at 0x29' and that would tell you nothing.")
        print("  Fix the wiring above first.")
        return []
    bus_recover()
    i2c = make_i2c()
    pins = all_low()

    pre = i2c.scan()
    if verbose:
        print("  everything in reset: %s" % [hex(a) for a in pre])
    if 0x29 in pre:
        print("  !! 0x29 answers with all XSHUT LOW -- one is unwired.")
        print("     Run test 3.")

    sensors = []
    for i, pin in enumerate(pins):
        pin.value(1)
        time.sleep_ms(BOOT_MS)
        try:
            if 0x29 not in i2c.scan():
                raise OSError("did not wake at 0x29")
            s = VL53L1X(i2c, 0x29)
            mid = s.model_id()
            if mid != MODEL_ID_L1X:
                print("  %-6s WARNING model id 0x%04X, expected 0x%04X"
                      % (NAMES[i], mid, MODEL_ID_L1X))
                print("         probably a VL53L0X -- wrong driver entirely")
            s.init(mode)
            s.set_address(ADDRESSES[i])
            s.start()
            sensors.append(s)
            if verbose:
                print("  %-6s XSHUT%-3d -> 0x%02X  id=0x%04X  ok"
                      % (NAMES[i], XSHUT[i], ADDRESSES[i], mid))
        except Exception as e:
            sensors.append(None)
            print("  %-6s XSHUT%-3d -> FAILED: %s" % (NAMES[i], XSHUT[i], e))
            pin.value(0)
            time.sleep_ms(BOOT_MS)

    S["i2c"], S["sensors"] = i2c, sensors
    alive = sum(1 for s in sensors if s)
    if verbose:
        print("  bus now: %s" % [hex(a) for a in i2c.scan()])
        print("  %d of %d live" % (alive, N_SENSORS))
        if alive < N_SENSORS:
            print("\n  -> test 3 names the bad wire, test 4 diagnoses one board")
    if alive:
        led_all(COL_CLEAR if alive == N_SENSORS else COL_FAULT)
        time.sleep(1)
        led_off()
    return sensors


def need():
    if not S["sensors"] or not any(S["sensors"]):
        print("\n  run test 5 (bring up) first")
        return None
    return S["sensors"]


def read_all(sensors):
    out = []
    for s in sensors:
        if s is None:
            out.append(None)
            continue
        try:
            if s.data_ready():
                mm = s.distance()
                if mm is not None and mm < SATURATE_MM:
                    mm = 0
                out.append(mm)
            else:
                out.append(None)
        except OSError:
            out.append(None)
    return out


# ===================================================================
# TEST 6 -- model ID of every sensor
# ===================================================================
def t6_model_ids():
    print("\n=== TEST 6: model ID check =================================")
    print("  0xEACC = VL53L1X (correct driver)")
    print("  0x00EE = VL53L0X (WRONG chip, looks identical on the silkscreen)\n")
    from vl53l1x import VL53L1X
    i2c = make_i2c(100_000)
    pins = all_low()
    for i, pin in enumerate(pins):
        pin.value(1)
        time.sleep_ms(BOOT_MS)
        try:
            mid = VL53L1X(i2c, 0x29).model_id()
            tag = "VL53L1X ok" if mid == MODEL_ID_L1X else "*** NOT AN L1X ***"
            print("  %-6s id=0x%04X   %s" % (NAMES[i], mid, tag))
        except Exception as e:
            print("  %-6s could not read: %s" % (NAMES[i], e))
        pin.value(0)
        time.sleep_ms(BOOT_MS)
    for p in pins:
        p.value(1)


# ===================================================================
# TEST 7 -- one sensor at a time  (catches swapped cables)
# ===================================================================
def t7_one_at_a_time():
    sensors = need()
    if not sensors:
        return
    print("\n=== TEST 7: one at a time ==================================")
    print("  Put your hand in front of the sensor NAMED below.")
    print("  If a DIFFERENT one reacts, your cables are swapped -- and no")
    print("  amount of code can detect that for you.\n")
    for i, s in enumerate(sensors):
        if s is None:
            print("  %-6s SKIPPED (did not come up)" % NAMES[i])
            continue
        print("  --> %s   (XSHUT GPIO%d, 0x%02X)  6 s"
              % (NAMES[i].upper(), XSHUT[i], ADDRESSES[i]))
        seen = None
        t0 = time.ticks_ms()
        nxt = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 6000:
            try:
                if s.data_ready():
                    mm = s.distance()
                    seen = 0 if (mm is not None and mm < SATURATE_MM) else mm
            except OSError:
                pass
            if time.ticks_diff(time.ticks_ms(), nxt) >= 0:
                nxt = time.ticks_add(time.ticks_ms(), PRINT_MS)
                print("      %s cm  |%s|" % (cm(seen), bar(seen)))
            time.sleep_ms(LOOP_MS)
        print()


# ===================================================================
# TEST 8 -- live view, all sensors
# ===================================================================
def t8_live(seconds=30):
    sensors = need()
    if not sensors:
        return
    n = len(sensors)
    tr = [ZoneTrack(NAMES[i]) for i in range(n)]
    print("\n=== TEST 8: live view ======================================")
    print("  all distances in cm. %d s. Ctrl+C to stop.\n" % seconds)
    last = [None] * n
    t0 = time.ticks_ms()
    nxt = time.ticks_ms()
    try:
        while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
            for i, mm in enumerate(read_all(sensors)):
                if mm is not None:
                    last[i] = mm
                    z = tr[i].update(mm)
                    if z:
                        print("      >> %-6s %s" % (NAMES[i], z))
            if time.ticks_diff(time.ticks_ms(), nxt) >= 0:
                nxt = time.ticks_add(time.ticks_ms(), PRINT_MS)
                print("  " + " | ".join("%-5s%s" % (NAMES[i][:5], cm(last[i]))
                                        for i in range(n)))
            time.sleep_ms(LOOP_MS)
    except KeyboardInterrupt:
        print("  (stopped)")


# ===================================================================
# TEST 9 -- calibrate + derive thresholds
# ===================================================================
def t9_calibrate(seconds=5):
    sensors = need()
    if not sensors:
        return
    n = len(sensors)
    print("\n=== TEST 9: calibration ====================================")
    print("  HOLD STILL. Nobody in front of the sensors. %d s.\n" % seconds)
    led_all(COL_CAL)
    for i in range(3, 0, -1):
        print("    starting in %d..." % i)
        time.sleep(1)

    samples = [[] for _ in range(n)]
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
        if time.ticks_diff(time.ticks_ms(), t0) > 500:
            for i, mm in enumerate(read_all(sensors)):
                if mm is not None and mm > SATURATE_MM:
                    samples[i].append(mm)
        time.sleep_ms(LOOP_MS)
    led_off()

    cal = {}
    print("  %-6s %5s %6s %6s %7s %6s  %s"
          % ("side", "n", "min", "max", "mean", "sd", "sees"))
    print("  " + "-" * 72)
    for i in range(n):
        st = stats(samples[i])
        if st is None or st["mean"] >= MAX_TRUST_MM:
            thr = DEFAULT_THRESHOLD_MM
        else:
            thr = int(min(max(st["mean"] - MARGIN_MM, MIN_THRESHOLD_MM),
                          MAX_THRESHOLD_MM))
        cal[NAMES[i]] = {"stats": st, "threshold_mm": thr}
        if st:
            print("  %-6s %5d %6d %6d %7.0f %6.1f  %s"
                  % (NAMES[i], st["n"], st["min"], st["max"],
                     st["mean"], st["sd"], verdict(st)))
        else:
            print("  %-6s %5d %6s %6s %7s %6s  %s"
                  % (NAMES[i], 0, "-", "-", "-", "-", verdict(None)))

    print("\n  thresholds (trigger when closer than this):")
    for i in range(n):
        t = cal[NAMES[i]]["threshold_mm"]
        print("    %-6s %4d mm  (%.0f cm)" % (NAMES[i], t, t / 10))
    print("\n  sd under ~10 mm indoors is healthy.")
    print("  above ~50 mm = bright light, dark/angled target, or loose wire.")

    S["cal"] = cal
    try:
        with open(CAL_FILE, "w") as fh:
            json.dump(cal, fh)
        print("  saved %s" % CAL_FILE)
    except OSError as e:
        print("  could not save: %s" % e)
    return cal


# ===================================================================
# TEST 10 -- range sweep, real min/max
# ===================================================================
def t10_sweep(seconds=25):
    sensors = need()
    if not sensors:
        return
    print("\n=== TEST 10: range sweep ===================================")
    for i in range(N_SENSORS):
        print("   %d  %s" % (i + 1, NAMES[i]))
    print("   a  all of them")
    c = ask("  which? ")
    if c is None:
        return
    idxs = list(range(N_SENSORS)) if c.lower() == "a" else None
    if idxs is None:
        try:
            idxs = [int(c) - 1]
        except ValueError:
            return

    for i in idxs:
        if i < 0 or i >= len(sensors) or sensors[i] is None:
            continue
        s = sensors[i]
        print("\n  --- %s ---" % NAMES[i].upper())
        print("  Start with your hand ON the lens. Move it away SLOWLY")
        print("  until the reading stops tracking you. %d s." % seconds)
        for k in range(3, 0, -1):
            print("    go in %d..." % k)
            time.sleep(1)
        vals, sat, drop = [], 0, 0
        t0 = time.ticks_ms()
        nxt = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
            try:
                if s.data_ready():
                    mm = s.distance()
                    if mm is None:
                        drop += 1
                    elif mm <= SATURATE_MM:
                        sat += 1
                    else:
                        vals.append(mm)
            except OSError:
                drop += 1
            if time.ticks_diff(time.ticks_ms(), nxt) >= 0:
                nxt = time.ticks_add(time.ticks_ms(), PRINT_MS)
                print("      %s cm" % cm(vals[-1] if vals else None))
            time.sleep_ms(LOOP_MS)
        st = stats(vals)
        if not st:
            print("  no valid samples -- check this sensor")
            continue
        S["sweeps"][NAMES[i]] = {"min_mm": st["min"], "max_mm": st["max"]}
        print("\n    usable min : %4d mm  (%.1f cm)" % (st["min"], st["min"] / 10))
        print("    usable max : %4d mm  (%.2f m)" % (st["max"], st["max"] / 1000))
        print("    %d valid, %d saturated, %d dropped" % (st["n"], sat, drop))
        if st["max"] < 1500:
            print("    NOTE under 1.5 m -- bright ambient light or dark target.")


# ===================================================================
# TEST 11 -- live detection, red / green
# ===================================================================
class Det:
    def __init__(self, thr):
        self.thr = thr
        self.present = False
        self._want = False
        self._n = 0
        self.last = None
        self.trips = 0

    def update(self, mm):
        if mm is None:
            return None
        self.last = mm
        if self.present:
            want = not (mm > self.thr + HYST_MM)
        else:
            want = SATURATE_MM < mm < self.thr
        if want != self._want:
            self._want, self._n = want, 1
        else:
            self._n += 1
        if want != self.present and self._n >= CONFIRM_N:
            self.present = want
            if want:
                self.trips += 1
            return want
        return None


def t11_detect(seconds=120):
    sensors = need()
    if not sensors:
        return
    cal = S["cal"]
    if cal is None:
        try:
            with open(CAL_FILE) as fh:
                cal = json.load(fh)
            S["cal"] = cal
        except (OSError, ValueError):
            print("\n  no calibration -- running test 9 first")
            cal = t9_calibrate()
            if cal is None:
                return

    n = len(sensors)
    dets = [Det((cal.get(NAMES[i]) or {}).get("threshold_mm",
                                             DEFAULT_THRESHOLD_MM))
            for i in range(n)]
    print("\n=== TEST 11: live detection ================================")
    print("  RED   = something in front of at least one sensor")
    print("  GREEN = all clear")
    print("  thresholds: %s"
          % ", ".join("%s %d" % (NAMES[i], dets[i].thr) for i in range(n)))
    print("  %d s. Ctrl+C to stop.\n" % seconds)

    last_any = None
    t0 = time.ticks_ms()
    nxt = time.ticks_ms()
    try:
        while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
            for i, mm in enumerate(read_all(sensors)):
                ch = dets[i].update(mm)
                if ch is True:
                    print("      >> %-6s OBJECT at %s cm"
                          % (NAMES[i], cm(dets[i].last)))
                elif ch is False:
                    print("      >> %-6s clear" % NAMES[i])
            any_p = any(d.present for d in dets)
            if any_p != last_any:
                led_all(COL_DETECT if any_p else COL_CLEAR)
                last_any = any_p
            if time.ticks_diff(time.ticks_ms(), nxt) >= 0:
                nxt = time.ticks_add(time.ticks_ms(), PRINT_MS)
                print("  " + " | ".join(
                    "%-5s%s%s" % (NAMES[i][:5], cm(dets[i].last),
                                  "*" if dets[i].present else " ")
                    for i in range(n))
                    + ("   DETECT" if any_p else "   clear"))
            time.sleep_ms(LOOP_MS)
    except KeyboardInterrupt:
        print("  (stopped)")
    led_off()
    print("\n  trips per side:")
    for i in range(n):
        print("    %-6s %d" % (NAMES[i], dets[i].trips))


# ===================================================================
# TEST 12 -- SHORT vs LONG
# ===================================================================
def t12_modes(seconds=8):
    from vl53l1x import SHORT, LONG
    print("\n=== TEST 12: SHORT vs LONG =================================")
    print("  Hold the scene still for both runs.")
    out = {}
    for label, mode in (("LONG", LONG), ("SHORT", SHORT)):
        print("\n  --- %s, %d s ---" % (label, seconds))
        sensors = t5_bring_up(mode=mode, verbose=False)
        vals = [[] for _ in sensors]
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
            for i, mm in enumerate(read_all(sensors)):
                if mm is not None and mm > SATURATE_MM:
                    vals[i].append(mm)
            time.sleep_ms(LOOP_MS)
        out[label] = {}
        for i in range(len(sensors)):
            st = stats(vals[i])
            out[label][NAMES[i]] = st
            if st:
                print("    %-6s mean %6.0f  sd %5.1f  max %5d"
                      % (NAMES[i], st["mean"], st["sd"], st["max"]))
            else:
                print("    %-6s no samples" % NAMES[i])
    print("\n  Higher max in LONG is expected. If SHORT has a much lower sd,")
    print("  your room is bright and SHORT is the honest choice for GENIE.")
    print("\n  re-run test 5 before the live tests.")
    S["sensors"] = []
    return out


# ===================================================================
# TEST 13 -- export results
# ===================================================================
def t13_export():
    print("\n=== TEST 13: export ========================================")
    cal = S["cal"] or {}
    try:
        with open(CSV_FILE, "w") as fh:
            fh.write("side,addr,xshut,baseline_mm,noise_sd_mm,"
                     "threshold_mm,min_mm,max_mm\n")
            for i in range(N_SENSORS):
                nm = NAMES[i]
                c = cal.get(nm) or {}
                st = c.get("stats") or {}
                sw = S["sweeps"].get(nm) or {}
                fh.write("%s,0x%02X,%d,%s,%s,%s,%s,%s\n" % (
                    nm, ADDRESSES[i], XSHUT[i],
                    "%.0f" % st["mean"] if st.get("mean") is not None else "",
                    "%.1f" % st["sd"] if st.get("sd") is not None else "",
                    c.get("threshold_mm", ""),
                    sw.get("min_mm", ""), sw.get("max_mm", "")))
        print("  wrote %s" % CSV_FILE)
        print("\n  Thonny -> MicroPython device -> right-click %s" % CSV_FILE)
        print("  -> Download to...  then open in Excel.")
    except OSError as e:
        print("  failed: %s" % e)


# ===================================================================
# TEST 0 -- run the whole sequence
# ===================================================================
def t0_everything():
    print("\n" + "=" * 60)
    print(" FULL SEQUENCE")
    print("=" * 60)
    t2_scan()
    pause()
    t3_xshut()
    pause()
    t5_bring_up()
    pause()
    t7_one_at_a_time()
    pause()
    t9_calibrate()
    pause()
    t11_detect(30)
    t13_export()
    print("\n  sequence complete.")


MENU = """
============================================================
 ToF ALL TESTS  --  %d sensors configured
============================================================
 DIAGNOSE
   1  find the status LED pin
   2  raw I2C scan
   3  XSHUT wiring diagnostic     <- names the bad wire
   4  deep diagnosis of ONE sensor <- when one will not wake
 BRING UP
   5  bring up the array           <- after EVERY reset
   6  model ID of every sensor     (0xEACC = correct chip)
 MEASURE
   7  one sensor at a time         (catches swapped cables)
   8  live view, all sensors
   9  calibrate + thresholds
  10  range sweep, real min/max
  11  live detection, red/green
  12  SHORT vs LONG comparison
  13  export results to CSV
 ---
   0  run the whole sequence
   q  quit
------------------------------------------------------------""" % N_SENSORS


def main():
    print("\n" + "=" * 60)
    print(" %s" % VERSION)
    print("=" * 60)
    try:
        import vl53l1x
        print("  vl53l1x driver: found")
    except ImportError:
        print("  !! vl53l1x.py is NOT on the board.")
        print("     Upload it, then run this again. Nothing else is needed.")
        return
    print("  sensors configured: %d  (edit N_SENSORS at the top)" % N_SENSORS)

    while True:
        print(MENU)
        c = ask("  select: ")
        if c is None or c.lower() == "q":
            led_off()
            print("bye")
            return
        fn = {"1": t1_find_led, "2": t2_scan, "3": t3_xshut,
              "4": t4_one_sensor, "5": t5_bring_up, "6": t6_model_ids,
              "7": t7_one_at_a_time, "8": t8_live, "9": t9_calibrate,
              "10": t10_sweep, "11": t11_detect, "12": t12_modes,
              "13": t13_export, "0": t0_everything}.get(c)
        if fn:
            try:
                fn()
            except KeyboardInterrupt:
                print("\n  (interrupted)")
            except Exception as e:
                print("\n  ERROR: %s: %s" % (type(e).__name__, e))
                print("  Nothing was damaged. Try test 2, then test 3.")
        else:
            print("  '%s'? pick 0-13 or q." % c)


if __name__ == "__main__":
    main()
