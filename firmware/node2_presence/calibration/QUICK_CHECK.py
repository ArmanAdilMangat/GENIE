# =============================================================================
# QUICK_CHECK.py  -  GENIE Node 2
# The 60-second sanity test. F5 in Thonny, wave your hand, watch the LED.
#
# Needs on board: vl53l1x.py
#
#   bring up -> 3 s baseline -> live loop
#   GREEN  = clear
#   RED    = something in front of any sensor
#
# No menu, no saved files, nothing clever. If this works, run
# CALIBRATE_AND_DETECT.py for the real thing.
# =============================================================================

from machine import Pin, I2C
import time

from vl53l1x import VL53L1X, SHORT, LONG

# --------------------------- CONFIG ------------------------------------------

SDA_PIN = 8
SCL_PIN = 9
XSHUT = (10, 11, 12, 13)
NAMES = ("front", "left", "right", "rear")
ADDRS = (0x30, 0x31, 0x32, 0x33)

N_SENSORS = 4          # set to how many are PHYSICALLY wired. Uses the first N.

# LED_SWEEP.py lit the LED while driving all of these at once; driving GPIO38
# alone does nothing. So the LED is NOT on 38 - we just don't know which it is.
# Fix: drive all candidates. Writing to a GPIO with nothing on it is harmless
# and costs ~30 us. Once you know the real pin, cut this down to just that one.
LED_PINS = (38, 48, 47, 21, 45)   # EXACTLY the set LED_SWEEP.py lit up with.
                                  # Do not trim this until you know which one.
LED_BRIGHT = 40

BLINK_RED = False      # False = solid on detect (easier to see in the box)
BLINK_MS = 400         # only used when BLINK_RED is True

# Colours. If the RED die on your WS2812 does not light (white looks CYAN in
# the self-test), just make DETECT_COLOUR blue - nothing else has to change.
CLEAR_COLOUR = (0, LED_BRIGHT, 0)          # green
DETECT_COLOUR = (LED_BRIGHT, 0, 0)         # red. Blue = (0, 0, LED_BRIGHT)

DIST_MODE = SHORT      # SHORT ~1.3 m, much better in bright light. LONG ~4 m.
I2C_FREQ = 400000

BASE_SAMPLES = 25      # baseline samples PER SENSOR (not seconds - see note)
MARGIN_MM = 150        # trigger this much closer than baseline
OPEN_TRIGGER = 1000    # trigger distance for a sensor with nothing in range

# --------------------------- LED ---------------------------------------------

# LED_MODE  "neo"  = onboard WS2812 on LED_PIN
#           "pins" = two ordinary LEDs, each GPIO -> 330R -> LED -> GND
#           "none" = console output only
LED_MODE = "neo"
RED_PIN = 14           # GPIO5 is taken by the WS2812 stick in 02_WS2812_NeoPixel
GREEN_PIN = 21
SWAP_RG = False        # set True if LED_TEST.py test 2 shows red/green swapped

nps = []
rled = None
gled = None

if LED_MODE == "neo":
    import neopixel
    for _p in LED_PINS:
        try:
            nps.append(neopixel.NeoPixel(Pin(_p, Pin.OUT), 1))
        except Exception as _e:
            print("  GPIO" + str(_p) + " unusable for LED:", _e)
elif LED_MODE == "pins":
    rled = Pin(RED_PIN, Pin.OUT, value=0)
    gled = Pin(GREEN_PIN, Pin.OUT, value=0)


_last = None


def led(r, g, b):
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
        for np in nps:
            np[0] = c
            np.write()
    elif LED_MODE == "pins":
        rled.value(1 if r else 0)
        gled.value(1 if g else 0)


def led_selftest():
    """NeoPixel never raises on a wrong pin. Only your eyes can confirm it."""
    print("LED self-test on GPIO " + str(LED_PINS))
    print("LOOK AT THE BOARD NOW - not at this console.")
    for t in (3, 2, 1):
        print("   starting in " + str(t) + " ...")
        time.sleep(1)
    for nm, c in (("RED", (LED_BRIGHT, 0, 0)),
                  ("GREEN", (0, LED_BRIGHT, 0)),
                  ("BLUE", (0, 0, LED_BRIGHT)),
                  ("WHITE", (LED_BRIGHT, LED_BRIGHT, LED_BRIGHT))):
        print("   " + nm)
        led(c[0], c[1], c[2])
        time.sleep(1.5)
    led(0, 0, 0)
    print("   off")
    print("")
    print("   WHITE looked CYAN / blue-green?  -> the RED die is dead.")
    print("      Set DETECT_COLOUR = (0, 0, LED_BRIGHT) at the top and")
    print("      detection will show BLUE instead. Nothing else changes.")
    print("   Nothing changed at all?  -> run LED_SWEEP.py (F5, no typing).")
    print("")


# --------------------------- HELPERS -----------------------------------------
# MicroPython str has no ljust/rjust. Pad by hand.

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


def read(s):
    """mm, or 0 if the reading is not trustworthy."""
    try:
        d = s.distance()          # returns None when range status != 0
    except Exception:
        return 0
    return d if d else 0


# --------------------------- BRING-UP ----------------------------------------

print("=" * 58)
print("QUICK CHECK - " + str(N_SENSORS) + " ToF")
print("=" * 58)

led_selftest()

# 1. wiring proof. A plain Pin.IN read cannot prove a wire exists.
a = Pin(SDA_PIN, Pin.IN, Pin.PULL_DOWN).value()
b = Pin(SCL_PIN, Pin.IN, Pin.PULL_DOWN).value()
print("SDA=" + str(a) + "  SCL=" + str(b), end="  ")
if a != 1 or b != 1:
    print("BAD - expected 1 1. Broken wire or no power. Stopping.")
    raise SystemExit
print("OK")

# 2. all XSHUT low, bus should go silent
xs = []
for i in range(N_SENSORS):
    xs.append(Pin(XSHUT[i], Pin.OUT, value=0))
time.sleep_ms(50)

i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
if len(i2c.scan()) != 0:
    print("WARN: bus not silent with all XSHUT low - an XSHUT wire is loose")

# 3. one at a time: wake, readdress, init, start
sensors = []
for i in range(N_SENSORS):
    xs[i].value(1)
    time.sleep_ms(60)
    if 0x29 not in i2c.scan():
        print("FAIL: " + NAMES[i] + " (XSHUT GPIO" + str(XSHUT[i]) +
              ") never appeared at 0x29")
        raise SystemExit
    s = VL53L1X(i2c, address=0x29)
    s.set_address(ADDRS[i])
    s.init(DIST_MODE)
    s.start()
    sensors.append(s)
    print("  " + padr(NAMES[i], 6) + " -> " + hex(ADDRS[i]) +
          "  id=" + hex(s.model_id()))

n = len(sensors)
print("bring-up OK")

# --------------------------- BASELINE ----------------------------------------

print("")
print("Learning the environment - KEEP THE AREA CLEAR")
print("(" + str(BASE_SAMPLES) + " samples per sensor. distance() blocks for")
print(" the ranging budget, ~100 ms, so expect roughly " +
      str(int(BASE_SAMPLES * n * 0.1)) + " s.)")
led(0, 0, LED_BRIGHT)

t0 = time.ticks_ms()
vals = []
for i in range(n):
    vals.append([])

# Sample-count based, NOT time based. A time box collects almost nothing
# because every distance() call blocks for the full ranging budget.
for k in range(BASE_SAMPLES):
    for i in range(n):
        d = read(sensors[i])
        if d:
            vals[i].append(d)

led(0, 0, 0)
print("took " + str(time.ticks_diff(time.ticks_ms(), t0) // 1000) + " s")

base = []
for i in range(n):
    v = sorted(vals[i])
    # OPEN only if there is essentially NOTHING coming back. A sensor with
    # even a marginal target (say 15% yield at 500 mm) must NOT be called
    # open - that hands it a 1000 mm trigger and it fires forever.
    if len(v) < max(3, BASE_SAMPLES // 10):
        base.append(0)                       # nothing in range -> open space
        print(padr(NAMES[i], 6) + " OPEN   nothing in range, trigger < " +
              str(OPEN_TRIGGER) + "mm   (" + str(len(v)) + "/" +
              str(BASE_SAMPLES) + " valid)")
    else:
        med = v[len(v) // 2]
        base.append(med)
        print(padr(NAMES[i], 6) + " WALL   base=" + padl(med, 5) +
              "mm  trigger < " + padl(med - MARGIN_MM, 5) + "mm   (" +
              str(len(v)) + "/" + str(BASE_SAMPLES) + " valid)")
        if med < 150:
            print("       ^ very close. Lens obstructed, or it is looking at")
            print("         the box wall / your own frame.")

# --------------------------- LIVE --------------------------------------------

print("")
print("=" * 58)
print("LIVE - put your hand in front of a sensor. Ctrl-C to stop.")
print("=" * 58)

last = 0
blink = False
bt = 0

try:
    while True:
        now = time.ticks_ms()
        hit = False
        row = ""

        for i in range(n):
            d = read(sensors[i])
            if base[i] == 0:
                h = (d > 0) and (d < OPEN_TRIGGER)
            else:
                h = (d > 0) and (d < base[i] - MARGIN_MM)
            if h:
                hit = True
            row += padr(NAMES[i][:2] + ("#" if h else ".") +
                        padl(d if d else "--", 5), 10)

        if hit:
            if BLINK_RED:
                if time.ticks_diff(now, bt) > BLINK_MS:
                    bt = now
                    blink = not blink
                    if blink:
                        led(DETECT_COLOUR[0], DETECT_COLOUR[1], DETECT_COLOUR[2])
                    else:
                        led(0, 0, 0)
            else:
                led(DETECT_COLOUR[0], DETECT_COLOUR[1], DETECT_COLOUR[2])
        else:
            blink = False
            led(CLEAR_COLOUR[0], CLEAR_COLOUR[1], CLEAR_COLOUR[2])

        if time.ticks_diff(now, last) > 250:
            last = now
            print(row + ("   <<< DETECT" if hit else ""))

        # No sleep here on purpose: distance() already blocks for the ranging
        # budget, so the loop is paced by the sensors at roughly 2-3 Hz.

except KeyboardInterrupt:
    led(0, 0, 0)
    for s in sensors:
        s.stop()
    print("")
    print("stopped")
