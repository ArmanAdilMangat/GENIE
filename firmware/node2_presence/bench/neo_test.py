"""WS2812 / NeoPixel 8-LED stick test — ESP32-S3, MicroPython.

Self-contained. `neopixel` is built into MicroPython, nothing to upload.
Thonny: open and press F5.

BRIGHTNESS is capped on purpose. See README.md before raising it.
"""

from machine import Pin
from neopixel import NeoPixel
import time

PIN = 5           # DIN of the first stick
N = 8             # 8 per stick; set to 8 * (number of chained sticks)
BRIGHTNESS = 40   # 0-255. Keep <= 60 while powering from the ESP32 board.

np = NeoPixel(Pin(PIN, Pin.OUT), N)


def s(c):
    """Scale a colour by BRIGHTNESS."""
    return (c[0] * BRIGHTNESS // 255,
            c[1] * BRIGHTNESS // 255,
            c[2] * BRIGHTNESS // 255)


def fill(c, scale=True):
    col = s(c) if scale else c
    for i in range(N):
        np[i] = col
    np.write()


def off():
    fill((0, 0, 0), scale=False)


def wheel(p):
    p %= 255
    if p < 85:
        return (255 - p * 3, p * 3, 0)
    if p < 170:
        p -= 85
        return (0, 255 - p * 3, p * 3)
    p -= 170
    return (p * 3, 0, 255 - p * 3)


def test_colours():
    """R, G, B, white. If red and green swap, the strip is RGB not GRB."""
    for name, c in (("red", (255, 0, 0)), ("green", (0, 255, 0)),
                    ("blue", (0, 0, 255)), ("white", (255, 255, 255))):
        print("  ", name)
        fill(c)
        time.sleep(0.8)
    off()


def test_chase():
    """One LED at a time. Confirms count and which end DIN is on."""
    for i in range(N):
        np[i] = s((255, 255, 255))
        np.write()
        time.sleep(0.12)
        np[i] = (0, 0, 0)
    np.write()


def test_index():
    """Lights LED 0 red and the last LED blue. Tells you the direction."""
    off()
    np[0] = s((255, 0, 0))
    np[N - 1] = s((0, 0, 255))
    np.write()
    time.sleep(2)
    off()


def rainbow(cycles=2, delay_ms=8):
    for j in range(255 * cycles):
        for i in range(N):
            np[i] = s(wheel((i * 256 // N) + j))
        np.write()
        time.sleep_ms(delay_ms)
    off()


def bar(pct, colour=(0, 255, 0)):
    """Level meter across the stick. pct 0-100. Reuse for sensor readouts."""
    lit = pct * N // 100
    for i in range(N):
        np[i] = s(colour) if i < lit else (0, 0, 0)
    np.write()


# --- status patterns, reused later by the fingerprint node ---

def ok_sweep():
    off()
    for i in range(N):
        np[i] = s((0, 255, 0))
        np.write()
        time.sleep_ms(40)
    time.sleep(0.6)
    off()


def reject_flash(times=3):
    for _ in range(times):
        fill((255, 0, 0))
        time.sleep_ms(150)
        off()
        time.sleep_ms(150)


if __name__ == "__main__":
    try:
        print("WS2812 test on GPIO%d, %d LEDs, brightness %d" % (PIN, N, BRIGHTNESS))
        print("1. colours")
        test_colours()
        print("2. index (LED0 red, last blue)")
        test_index()
        print("3. chase")
        test_chase()
        print("4. bar sweep")
        for p in range(0, 101, 5):
            bar(p)
            time.sleep_ms(60)
        off()
        print("5. rainbow")
        rainbow()
        print("6. status patterns")
        ok_sweep()
        reject_flash()
        print("done.")
    finally:
        off()
