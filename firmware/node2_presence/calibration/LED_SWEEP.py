# =============================================================================
# LED_SWEEP.py  -  GENIE Node 2
# ZERO INTERACTION. Press F5 and watch the board. Do not type anything.
#
# Needs nothing on the board. Imports no drivers. Touches no sensor.
#
# Runs for about 90 s:
#   PHASE 0  prints board + firmware info
#   PHASE 1  drives ALL candidate pins at once  -> is there a LED at all?
#   PHASE 2  one pin at a time                  -> which GPIO is it on?
#   PHASE 3  full-brightness white              -> last resort, hard to miss
#
# WHERE TO LOOK: the RGB LED is a single small WHITE SQUARE (about 3 mm) on
# the top of the board, usually next to the BOOT/RESET buttons. It is NOT the
# tiny always-on red/green power LED near the USB sockets - that one never
# changes. If the board is buried under the wiring loom, pull it out first.
# =============================================================================

from machine import Pin
import time
import sys

CANDIDATES = (38, 48, 47, 21, 45)
BRIGHT = 60
DWELL = 2.0            # seconds per colour


def banner(t):
    print("")
    print("=" * 62)
    print(t)
    print("=" * 62)


# --------------------------------------------------------------- PHASE 0

banner("PHASE 0 - environment")

try:
    import os
    u = os.uname()
    print("  sysname  : " + u.sysname)
    print("  release  : " + u.release)
    print("  machine  : " + u.machine)
except Exception as e:
    print("  os.uname failed:", e)

try:
    import neopixel
    print("  neopixel : present")
except Exception as e:
    print("  neopixel : MISSING ->", e)
    print("  Stop. Your firmware has no neopixel module. Reflash.")
    raise SystemExit

print("")
print("  If you can read this line in the Thonny Shell, the script IS")
print("  running and the serial link is fine. Any 'nothing happened'")
print("  from here on is about the LED, not about the code.")

# --------------------------------------------------------------- PHASE 1

banner("PHASE 1 - all candidate pins at once")
print("  Driving GPIO " + str(CANDIDATES) + " simultaneously.")
print("  If the onboard LED is on ANY of them, it will light now.")
print("  WATCH THE BOARD.")
print("")

pixels = []
for p in CANDIDATES:
    try:
        pixels.append((p, neopixel.NeoPixel(Pin(p, Pin.OUT), 1)))
    except Exception as e:
        print("  GPIO" + str(p) + " unusable:", e)


def all_write(col):
    for p, np in pixels:
        np[0] = col
        np.write()


for name, col in (("RED", (BRIGHT, 0, 0)),
                  ("GREEN", (0, BRIGHT, 0)),
                  ("BLUE", (0, 0, BRIGHT)),
                  ("OFF", (0, 0, 0))):
    print("  -> " + name)
    all_write(col)
    time.sleep(DWELL)

print("")
print("  Saw nothing in PHASE 1?")
print("  Then either the WS2812 is not populated on this board (common on")
print("  clones), or it is on a GPIO not in the candidate list, or you are")
print("  looking at the wrong component. Skip to the notes at the end.")

# --------------------------------------------------------------- PHASE 2

banner("PHASE 2 - one pin at a time")
print("  Each pin gets red, green, blue. Note which GPIO makes it change.")
print("")

for p, np in pixels:
    print("  ---- GPIO" + str(p) + " ----")
    for name, col in (("red", (BRIGHT, 0, 0)),
                      ("green", (0, BRIGHT, 0)),
                      ("blue", (0, 0, BRIGHT))):
        print("       " + name)
        np[0] = col
        np.write()
        time.sleep(DWELL)
    np[0] = (0, 0, 0)
    np.write()
    time.sleep(0.5)

# --------------------------------------------------------------- PHASE 3

banner("PHASE 3 - full brightness white, all pins, 6 s")
print("  Maximum visibility. If anything at all is going to be seen")
print("  through the box and the wiring, it is this.")
all_write((255, 255, 255))
time.sleep(6)
all_write((0, 0, 0))

# --------------------------------------------------------------- RESULT

banner("DONE - what your result means")
print("""
  Saw a colour on ONE pin
      That is your LED_PIN. Put it in QUICK_CHECK.py and
      CALIBRATE_AND_DETECT.py.

  Saw red where the script said green (or vice versa)
      Clone with RGB byte order instead of GRB.
      Set SWAP_RG = True in both scripts.

  Saw absolutely nothing in any phase
      Check, in this order:
      1. Is the ESP32 buried under the wiring / inside the box? Pull it
         out and repeat. The RGB LED is small and easily hidden.
      2. Are you watching the right part? The RGB LED is a white square
         near the BOOT/RESET buttons, NOT the power LED by the USB ports.
      3. Look at the board with a phone camera in a dark room - a very
         dim WS2812 shows up on camera before it does to the eye.
      4. If still nothing: this board has no WS2812 fitted. Very common
         on cheap DevKitC-1 clones. Use two ordinary LEDs instead -
         set LED_MODE = "pins" in the other two scripts.

  Nothing printed at all in the Shell
      The script never ran. In Thonny check: interpreter is
      MicroPython (ESP32), the right COM port is selected, and the
      Shell pane is visible at the bottom.
""")
