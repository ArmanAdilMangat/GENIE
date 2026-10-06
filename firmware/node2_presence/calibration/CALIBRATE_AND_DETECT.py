# =============================================================================
# GENIE Node 2 - ToF environment calibration + presence LED
# ESP32-S3 DevKitC-1 / MicroPython v1.27.0 / Thonny (F5)
#
# Needs on board: vl53l1x.py      <- the ONLY upload, per project convention
# Everything else is inlined here.
#
# What it does:
#   - learns the static environment per sensor (baseline + noise)
#   - saves it to flash so it survives a reboot
#   - live loop: RED blink if anything intrudes, solid GREEN if clear
# =============================================================================

from machine import Pin, I2C
import time
import json

try:
    from vl53l1x import VL53L1X, SHORT, LONG
except ImportError:
    VL53L1X = None
    SHORT = 0
    LONG = 1

# --------------------------- CONFIG ------------------------------------------

SDA_PIN = 8
SCL_PIN = 9
XSHUT = (10, 11, 12, 13)
NAMES = ("front", "left", "right", "rear")
ADDRS = (0x30, 0x31, 0x32, 0x33)
N_SENSORS = 4

# LED_SWEEP.py lit the LED while driving all of these at once; driving GPIO38
# alone does nothing. So the LED is NOT on 38 - we just don't know which it is.
# Fix: drive all candidates. Writing to a GPIO with nothing on it is harmless
# and costs ~30 us. Once you know the real pin, cut this down to just that one.
LED_PINS = (38, 48, 47, 21, 45)   # EXACTLY the set LED_SWEEP.py lit up with.
                                  # Do not trim this until you know which one.
LED_BRIGHT = 40       # 0-255. Keep low, the onboard RGB is blinding at 255.

I2C_FREQ = 400000     # drop to 100000 if the bus is flaky on breadboard
DIST_MODE = SHORT     # SHORT ~1.3 m, far better ambient immunity. LONG ~4 m.

BASELINE_FILE = "tof_baseline.json"

# Colours. If the RED die on your WS2812 does not light (white looks CYAN in
# the self-test), just make DETECT_COLOUR blue - nothing else has to change.
CLEAR_COLOUR = (0, LED_BRIGHT, 0)          # green
DETECT_COLOUR = (LED_BRIGHT, 0, 0)         # red. Blue = (0, 0, LED_BRIGHT)

# calibration
CAL_SAMPLES = 40      # samples per sensor. Each read blocks ~100 ms, so 40
                      # per sensor is already ~4 s each - 80 was needless.
CAL_DELAY_MS = 0      # distance() already blocks for the ranging budget.
                      # An extra sleep here just makes calibration slower.
CAL_COUNTDOWN = 10    # seconds to GET OUT OF RANGE OF EVERY SENSOR.
                      # You standing in one sensor's cone during calibration
                      # is the single most common way to ruin a baseline.

MOVING_NOISE_MM = 25  # spread above this at low yield = a moving object was
                      # in the cone, not a surface. See the note in calibrate().

# Manual overrides by sensor index: 0=front 1=left 2=right 3=rear.
# Use when the automatic call is wrong - e.g. FORCE_OPEN = (1,) if 'left'
# faces open space but keeps being classified as a wall.
FORCE_OPEN = ()
FORCE_WALL = ()

# detection
MAX_VALID_MM = 3500   # above this = out of range / no target
OPEN_TRIGGER = 1200   # mm - trigger distance for a sensor with no wall in view
OPEN_CLEAR = 1400     # mm - must retreat past this to clear (hysteresis)
K_SIGMA = 6.0         # margin = K_SIGMA * measured noise
MIN_MARGIN_MM = 80    # never trigger on less than this much change
HYST = 0.6            # clear threshold = baseline - margin*HYST
N_CONSEC = 2          # consecutive frames needed to change state
DRIFT_ALPHA = 0.02    # slow baseline adaptation, only while CLEAR
BLINK_RED = False     # False = solid red on detect (easier to see in the box)
BLINK_MS = 400        # red blink half-period, only used when BLINK_RED is True

# --------------------------- SMALL HELPERS -----------------------------------
# MicroPython str has no rjust/ljust/zfill and % has no * width. Pad by hand.

def padr(s, n):
    s = str(s)
    while len(s) < n:
        s = s + " "
    return s


def padl(s, n):
    s = str(s)
    while len(s) < n:
        s = " " + s
    return s


def line(c="-", n=62):
    print(c * n)


# --------------------------- LED ---------------------------------------------

# LED_MODE  "neo"  = onboard WS2812 on LED_PIN
#           "pins" = two ordinary LEDs, each GPIO -> 330R -> LED -> GND
#           "none" = console output only
LED_MODE = "neo"
RED_PIN = 14           # GPIO5 is taken by the WS2812 stick in 02_WS2812_NeoPixel
GREEN_PIN = 21
SWAP_RG = False        # True if LED_TEST.py test 2 shows red/green swapped

_nps = []
_rled = None
_gled = None


def led_init():
    """NeoPixel NEVER raises on a wrong pin, so this also runs a self-test.
    Only your eyes can tell you whether the LED is really on that GPIO."""
    global _rled, _gled
    if LED_MODE == "neo":
        import neopixel
        for p in LED_PINS:
            try:
                _nps.append(neopixel.NeoPixel(Pin(p, Pin.OUT), 1))
            except Exception as e:
                print("  GPIO" + str(p) + " unusable for LED:", e)
    elif LED_MODE == "pins":
        _rled = Pin(RED_PIN, Pin.OUT, value=0)
        _gled = Pin(GREEN_PIN, Pin.OUT, value=0)
    else:
        return False

    print("LED self-test on GPIO " + str(LED_PINS))
    print("LOOK AT THE BOARD NOW - not at this console.")
    print("(ignore the small always-on power LED, it never changes)")
    for t in (3, 2, 1):
        print("   starting in " + str(t) + " ...")
        time.sleep(1)
    for nm, c in (("RED", (LED_BRIGHT, 0, 0)),
                  ("GREEN", (0, LED_BRIGHT, 0)),
                  ("BLUE", (0, 0, LED_BRIGHT)),
                  ("WHITE", (LED_BRIGHT, LED_BRIGHT, LED_BRIGHT))):
        print("   " + nm)
        led_rgb(c[0], c[1], c[2])
        time.sleep(1.5)
    led_off()
    print("   off")
    print("")
    print("   WHITE looked CYAN / blue-green?  -> the RED die is dead.")
    print("      Set DETECT_COLOUR = (0, 0, LED_BRIGHT) at the top and")
    print("      detection will show BLUE instead. Nothing else changes.")
    print("   Nothing changed at all?  -> run LED_SWEEP.py (F5, no typing).")
    print("")
    return True


_last = None


def led_rgb(r, g, b):
    """Cached - only writes when the colour actually changes. Hammering a
    WS2812 every 20 ms adds jitter to the sensor loop for no benefit."""
    global _last
    if SWAP_RG:
        r, g = g, r
    c = (r, g, b)
    if c == _last:
        return
    _last = c
    if LED_MODE == "neo":
        for np in _nps:
            np[0] = c
            np.write()
    elif LED_MODE == "pins":
        if _rled is None:
            return
        _rled.value(1 if r else 0)
        _gled.value(1 if g else 0)


def led_off():
    led_rgb(0, 0, 0)


def led_green():
    """The CLEAR state. Named green by habit - the colour is configurable."""
    led_rgb(CLEAR_COLOUR[0], CLEAR_COLOUR[1], CLEAR_COLOUR[2])


def led_red():
    """The DETECT state. Switch DETECT_COLOUR if your red die is dead."""
    led_rgb(DETECT_COLOUR[0], DETECT_COLOUR[1], DETECT_COLOUR[2])


def led_blue():
    led_rgb(0, 0, LED_BRIGHT)


# --------------------------- BUS / BRING-UP ----------------------------------

def check_bus():
    """Internal pull-down test. A plain Pin.IN read cannot prove a wire exists."""
    a = Pin(SDA_PIN, Pin.IN, Pin.PULL_DOWN).value()
    b = Pin(SCL_PIN, Pin.IN, Pin.PULL_DOWN).value()
    print("SDA(GPIO" + str(SDA_PIN) + ")=" + str(a) +
          "  SCL(GPIO" + str(SCL_PIN) + ")=" + str(b))
    if a == 1 and b == 1:
        print("OK - both lines have a real external pull-up.")
        return True
    print("BAD - expected 1 1.")
    if a == 0:
        print("  SDA has no pull-up: broken SDA wire, or sensors unpowered.")
    if b == 0:
        print("  SCL has no pull-up: broken SCL wire.")
    print("  Replace the wire. Do not re-seat it.")
    return False


def unjam(n=9):
    """Nine clock pulses frees a slave holding SDA low after a mid-txn reset."""
    scl = Pin(SCL_PIN, Pin.OUT, value=1)
    for _ in range(n):
        scl.value(0)
        time.sleep_us(5)
        scl.value(1)
        time.sleep_us(5)


def read_mm(s):
    """mm, or 0 if not trustworthy. Driver returns None on bad range status."""
    try:
        d = s.distance()
    except Exception:
        return 0
    return d if d else 0


def bringup():
    """ToF addresses live in RAM. This MUST run at the top of every boot."""
    if VL53L1X is None:
        print("FAIL: vl53l1x.py is not on the board.")
        return None

    if not check_bus():
        return None

    unjam()

    xs = []
    for i in range(N_SENSORS):
        xs.append(Pin(XSHUT[i], Pin.OUT, value=0))
    time.sleep_ms(50)

    i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)

    found = i2c.scan()
    if len(found) != 0:
        print("WARN: bus not silent with all XSHUT low:", [hex(a) for a in found])
        print("      an XSHUT wire is probably not connected.")

    sensors = []
    for i in range(N_SENSORS):
        xs[i].value(1)
        time.sleep_ms(60)
        if 0x29 not in i2c.scan():
            print("FAIL: " + NAMES[i] + " (XSHUT GPIO" + str(XSHUT[i]) +
                  ") did not appear at 0x29")
            return None
        try:
            s = VL53L1X(i2c, address=0x29)
            s.set_address(ADDRS[i])
            s.init(DIST_MODE)
            s.start()
        except OSError as e:
            print("FAIL: " + NAMES[i] + " init: " + str(e))
            return None
        if ADDRS[i] not in i2c.scan():
            print("FAIL: " + NAMES[i] + " did not move to " + hex(ADDRS[i]))
            return None
        sensors.append(s)
        print("  " + padr(NAMES[i], 6) + " -> " + hex(ADDRS[i]) +
              "  id=" + hex(s.model_id()))

    print("bring-up complete, " + str(len(sensors)) + " sensors live")
    return sensors


# --------------------------- CALIBRATION -------------------------------------

def median(v):
    v = sorted(v)
    return v[len(v) // 2]


def b_window(med, margin):
    """How much room is left between the trigger point and the sensor face.
    Small window = the sensor is staring at something close, so there is
    almost nowhere for an intruder to stand and be seen."""
    return med - margin


def calibrate(sensors):
    line("=")
    print("CALIBRATION - learning the environment")
    line("=")
    print("Put GENIE in its FINAL position, then STEP OUT OF RANGE OF")
    print("EVERY SENSOR - including the ones pointing at you.")
    print("Anything standing here now becomes 'normal' and turns invisible.")
    for t in range(CAL_COUNTDOWN, 0, -1):
        led_blue()
        print("  starting in " + str(t) + " ...")
        time.sleep_ms(500)
        led_off()
        time.sleep_ms(500)

    base = []
    for i in range(len(sensors)):
        led_blue()
        vals = []
        for _ in range(CAL_SAMPLES):
            d = read_mm(sensors[i])
            if d and 0 < d < MAX_VALID_MM:
                vals.append(d)
            time.sleep_ms(CAL_DELAY_MS)
        led_off()

        yield_pct = int(100 * len(vals) / CAL_SAMPLES)

        # Spread of the valid samples, even if there are only a handful.
        if len(vals) >= 3:
            med = median(vals)
            noise = median([abs(v - med) for v in vals]) * 1.4826
        else:
            med = 0
            noise = 0.0

        # ---------------------------------------------------------------
        # Low yield is AMBIGUOUS. It means one of two opposite things:
        #
        #   (a) a weak but STATIC target - dark, glossy or steeply angled.
        #       Valid samples cluster tightly, like the solid walls do
        #       (noise ~1 mm). This must become WALL.
        #
        #   (b) OPEN SPACE with something MOVING through it during
        #       calibration - usually the person running the test. Valid
        #       samples are scattered over a wide range. This must stay
        #       OPEN, otherwise that person becomes the baseline and is
        #       invisible for ever after.
        #
        # Yield alone cannot tell these apart. SPREAD can: a real surface
        # reads to about a millimetre, a moving body does not.
        # ---------------------------------------------------------------
        moving = noise > MOVING_NOISE_MM

        if i in FORCE_OPEN:
            mode = "open"
            why = "forced open by FORCE_OPEN"
        elif i in FORCE_WALL:
            mode = "wall"
            why = "forced wall by FORCE_WALL"
        elif yield_pct < 10 or len(vals) < 3:
            mode = "open"
            why = "nothing came back"
        elif yield_pct < 50 and moving:
            mode = "open"
            why = "few reads, spread " + str(int(noise)) + "mm - something " \
                  "was MOVING, not a surface"
        elif yield_pct < 50:
            mode = "wall"
            why = "few reads but tight spread - weak static target"
        else:
            mode = "wall"
            why = ""

        if mode == "open":
            base.append({"name": NAMES[i], "mode": "open",
                         "base": OPEN_TRIGGER, "noise": noise,
                         "margin": 0.0, "yield": yield_pct})
            print(padr(NAMES[i], 6) + " OPEN   trigger at " +
                  str(OPEN_TRIGGER) + "mm   (yield " + str(yield_pct) +
                  "%, spread " + str(int(noise)) + "mm)")
            if why:
                print("       " + why)
            if yield_pct >= 10:
                print("       If this sensor really is aimed at a surface,")
                print("       add its index to FORCE_WALL and recalibrate.")
            continue

        margin = K_SIGMA * noise
        if margin < MIN_MARGIN_MM:
            margin = MIN_MARGIN_MM

        base.append({"name": NAMES[i], "mode": "wall",
                     "base": med, "noise": noise,
                     "margin": margin, "yield": yield_pct})

        print(padr(NAMES[i], 6) + " WALL  base=" + padl(med, 5) + "mm  " +
              "noise=" + padl(int(noise), 4) + "mm  " +
              "trip<" + padl(int(med - margin), 5) + "mm  " +
              "(yield " + str(yield_pct) + "%)")
        if why:
            print("       " + why)

        # sanity checks worth paying attention to
        if med < 150 and noise < 5:
            print("       ^ WARNING: very close and dead quiet.")
            print("         Lens is almost certainly obstructed - acrylic,")
            print("         tape or the enclosure wall. Cut a hole for it.")
        elif yield_pct < 50:
            print("       ^ CHECK THIS ONE. Only " + str(yield_pct) +
                  "% of reads came back, but they")
            print("         were tight, so it was called a surface. If this")
            print("         sensor is actually pointing at open space, add")
            print("         its index to FORCE_OPEN and recalibrate.")
        elif yield_pct < 70:
            print("       ^ WARNING: " + str(100 - yield_pct) +
                  "% dropped reads. Sunlight, a glossy/black surface,")
            print("         or a marginal I2C bus.")

        # A very tight detection window is easy to miss and hard to demo.
        if b_window(med, margin) < 250:
            print("       ^ NOTE: only " + str(int(med - margin)) +
                  " mm of space in front of this")
            print("         sensor before it trips. It is aimed at something")
            print("         " + str(int(med)) + " mm away, so nobody can be")
            print("         seen further out than that. Re-aim it at open")
            print("         space if you want a bigger detection zone.")

    line()
    return base


def save_baseline(base):
    try:
        f = open(BASELINE_FILE, "w")
        f.write(json.dumps(base))
        f.close()
        print("saved -> " + BASELINE_FILE)
    except Exception as e:
        print("save failed:", e)


def load_baseline():
    try:
        f = open(BASELINE_FILE, "r")
        b = json.loads(f.read())
        f.close()
        print("loaded baseline from " + BASELINE_FILE)
        return b
    except Exception:
        print("no saved baseline (" + BASELINE_FILE + ")")
        return None


def show_baseline(base):
    if not base:
        return
    line()
    print(padr("sensor", 8) + padr("mode", 6) + padl("base", 7) +
          padl("noise", 7) + padl("trip", 7))
    line()
    for b in base:
        print(padr(b["name"], 8) + padr(b["mode"], 6) +
              padl(int(b["base"]), 7) + padl(int(b["noise"]), 7) +
              padl(int(b["base"] - b["margin"]) if b["mode"] == "wall"
                   else OPEN_TRIGGER, 7))
    line()


# --------------------------- LIVE DETECTION ----------------------------------

def detect(sensors, base):
    n = len(sensors)
    state = [False] * n      # confirmed per-sensor detection
    count = [0] * n          # debounce counter
    last_print = 0
    blink_t = 0
    blink_on = False

    line("=")
    print("LIVE DETECTION - Ctrl-C to stop")
    print("RED blink = something in range   GREEN = clear")
    line("=")

    while True:
        now = time.ticks_ms()
        row = ""
        any_det = False

        for i in range(n):
            d = read_mm(sensors[i])
            b = base[i]
            valid = bool(d) and 0 < d < MAX_VALID_MM

            if b["mode"] == "open":
                trip = OPEN_TRIGGER
                clear = OPEN_CLEAR
            else:
                trip = b["base"] - b["margin"]
                clear = b["base"] - b["margin"] * HYST

            if state[i]:
                hit = valid and d < clear          # stay latched until it retreats
            else:
                hit = valid and d < trip

            if hit != state[i]:
                count[i] += 1
                if count[i] >= N_CONSEC:
                    state[i] = hit
                    count[i] = 0
            else:
                count[i] = 0

            # slow drift adaptation - only while genuinely clear
            if (not state[i]) and valid and b["mode"] == "wall":
                b["base"] = (1.0 - DRIFT_ALPHA) * b["base"] + DRIFT_ALPHA * d

            if state[i]:
                any_det = True

            mark = "#" if state[i] else "."
            row += padr(b["name"][:2] + mark + padl(d if valid else "--", 5), 10)

        # LED
        if any_det:
            if BLINK_RED:
                if time.ticks_diff(now, blink_t) > BLINK_MS:
                    blink_t = now
                    blink_on = not blink_on
                    if blink_on:
                        led_red()
                    else:
                        led_off()
            else:
                led_red()
        else:
            blink_on = False
            led_green()

        if time.ticks_diff(now, last_print) > 250:
            last_print = now
            print(row + ("  <<< DETECT" if any_det else ""))

        time.sleep_ms(20)


# --------------------------- MENU --------------------------------------------

def main():
    led_init()
    base = None
    sensors = None

    while True:
        line("=")
        print("GENIE Node 2 - ToF calibration")
        line("=")
        print(" 1  wiring check only (pull-down test)")
        print(" 2  bring up sensors")
        print(" 3  calibrate environment   (needs 2)")
        print(" 4  live detection          (needs 2 + a baseline)")
        print(" 5  show saved baseline")
        print(" 6  full run: bring up -> calibrate -> detect")
        print(" 0  quit")
        try:
            c = input("> ").strip()
        except KeyboardInterrupt:
            break

        if c == "1":
            check_bus()
        elif c == "2":
            sensors = bringup()
        elif c == "3":
            if sensors is None:
                print("run 2 first")
            else:
                base = calibrate(sensors)
                save_baseline(base)
        elif c == "4":
            if sensors is None:
                print("run 2 first")
                continue
            if base is None:
                base = load_baseline()
            if base is None:
                print("run 3 first")
                continue
            try:
                detect(sensors, base)
            except KeyboardInterrupt:
                led_off()
                print("\nstopped")
        elif c == "5":
            show_baseline(load_baseline())
        elif c == "6":
            sensors = bringup()
            if sensors is None:
                continue
            base = calibrate(sensors)
            save_baseline(base)
            try:
                detect(sensors, base)
            except KeyboardInterrupt:
                led_off()
                print("\nstopped")
        elif c == "0":
            led_off()
            break


main()
